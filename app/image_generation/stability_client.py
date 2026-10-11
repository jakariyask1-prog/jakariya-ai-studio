"""Stability AI Stable Image Core integration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import httpx

from app.utils.paths import get_generated_images_dir, load_environment


class StabilityImageClient:
    """Generate images with Stability AI and save them for chat display."""

    ENDPOINT = "https://api.stability.ai/v2beta/stable-image/generate/core"

    def __init__(self) -> None:
        load_environment()
        key = os.getenv("STABILITY_API_KEY", "").strip()
        if not key:
            try:
                from app.settings.settings_manager import SettingsManager
                prov = SettingsManager.instance().service.schema.providers.get("stability_ai")
                if prov and prov.api_key:
                    key = prov.api_key.strip()
            except Exception:
                pass
        self.api_key = key

    def generate(self, prompt: str, aspect_ratio: str = "1:1") -> Path:
        """Create one PNG/JPG image and return its local path.

        Order of attempts:
        1. Stability AI (if STABILITY_API_KEY is configured and has credits)
        2. Hugging Face Inference API (if HUGGINGFACE_API_KEY / HF_TOKEN is configured)
        3. Pollinations AI (with POLLINATIONS_API_KEY if configured, or public endpoint)
        """
        errors: list[str] = []

        # 1. Stability AI
        if self.api_key and len(self.api_key.strip()) > 5:
            payload = {
                "prompt": prompt.strip(),
                "aspect_ratio": aspect_ratio,
                "output_format": "png",
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "image/*",
                "Stability-Client-ID": "Jakariya AI Studio",
            }

            try:
                response = httpx.post(
                    self.ENDPOINT,
                    headers=headers,
                    data=payload,
                    files={"none": (None, "")},
                    timeout=90.0,
                )
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("image/") and response.content:
                        output_dir = get_generated_images_dir()
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / f"image_{uuid4().hex}.png"
                        output_path.write_bytes(response.content)
                        return output_path
                else:
                    errors.append(f"Stability AI: {self._error_message(response)}")
            except Exception as exc:
                errors.append(f"Stability AI connection error: {exc}")

        # 2. Hugging Face Inference Providers (FLUX.1-schnell)
        hf_token = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN") or ""
        if hf_token and len(hf_token.strip()) > 5:
            try:
                from huggingface_hub import InferenceClient
                providers = ["fal-ai", "together", "replicate", "black-forest-labs", "hyperbolic", "nebius"]
                for p in providers:
                    try:
                        client = InferenceClient(provider=p, api_key=hf_token.strip())
                        pil_img = client.text_to_image(prompt.strip(), model="black-forest-labs/FLUX.1-schnell")
                        if pil_img:
                            output_dir = get_generated_images_dir()
                            output_dir.mkdir(parents=True, exist_ok=True)
                            output_path = output_dir / f"image_{uuid4().hex}.jpg"
                            pil_img.save(str(output_path), "JPEG", quality=95)
                            return output_path
                    except Exception:
                        continue
                errors.append("Hugging Face: Inference providers currently busy or unreachable")
            except Exception as exc:
                errors.append(f"Hugging Face: {exc}")

        # 3. Pollinations AI (with optional key or public)
        pollinations_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
        try:
            from urllib.parse import quote
            encoded_prompt = quote(prompt.strip())
            headers = {}
            if pollinations_key:
                headers["Authorization"] = f"Bearer {pollinations_key}"
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
            response = httpx.get(url, headers=headers, timeout=60.0, follow_redirects=True)
            if response.status_code == 200 and response.content and len(response.content) > 1000:
                output_dir = get_generated_images_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"image_{uuid4().hex}.jpg"
                output_path.write_bytes(response.content)
                return output_path
            else:
                errors.append(f"Pollinations AI: HTTP {response.status_code}")
        except Exception as exc:
            errors.append(f"Pollinations AI error: {exc}")

        # If all providers failed, construct actionable error
        detailed_errors = " | ".join(errors) if errors else "No active image provider available."
        raise RuntimeError(
            f"Image generation failed: {detailed_errors}. "
            "Please check STABILITY_API_KEY credits at https://platform.stability.ai/account/credits "
            "or add a free HUGGINGFACE_API_KEY in .env."
        )

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        """Return a user-friendly API error without exposing credentials."""
        try:
            data = response.json()
        except ValueError:
            data = {}

        message = data.get("message") or data.get("error") or data.get("errors") or ""
        if isinstance(message, list):
            message = "; ".join(str(item) for item in message)
        if isinstance(message, dict):
            message = message.get("message", "")
        message = re.sub(r"Bearer\s+\S+", "Bearer [hidden]", str(message))

        if response.status_code in (401, 403):
            return "Stability API key was rejected. Check STABILITY_API_KEY in .env."
        if response.status_code == 402:
            return "Your Stability AI credits are exhausted. Add credits and try again."
        if response.status_code == 429:
            return "Stability AI rate limit reached. Please wait a minute and try again."
        if response.status_code == 400 and message:
            return f"Stability AI could not process this image request: {message}"
        return f"Image generation failed (HTTP {response.status_code}). Please try again."
