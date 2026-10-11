"""Unit tests for Image Enhancement routing, local clarity processing, and worker integration."""

import base64
import io
from pathlib import Path
import pytest
from PIL import Image

from app.image_generation.router import (
    is_image_enhancement_request,
    is_image_generation_request,
    extract_image_payload,
)
from app.image_generation.image_enhancer import ImageEnhancer
from app.chat.worker import ClaudeWorker, ChatRequest


def test_is_image_enhancement_request():
    """Verify various English, Banglish, and Bengali enhancement prompts."""
    # The user's exact prompts
    assert is_image_enhancement_request("pic aro clear and profestional kore dau")
    assert is_image_enhancement_request("please same image create like more clear and profestional.")
    assert is_image_enhancement_request("make this image clear and professional")
    assert is_image_enhancement_request("sharpen this portrait and upscale")
    assert is_image_enhancement_request("enhance resolution and clarity")
    assert is_image_enhancement_request("ছবির কোয়ালিটি আরও ক্লিয়ার করে দাও")
    assert is_image_enhancement_request("এই ছবিটা শার্প ও প্রফেশনাল করো")

    # Non-enhancement conversational prompts
    assert not is_image_enhancement_request("what is the weather today in Dhaka?")
    assert not is_image_enhancement_request("write a python script for sorting")
    assert not is_image_enhancement_request("explain quantum physics")


def test_extract_image_payload():
    """Verify text and binary image decoding from multimodal structure."""
    dummy_img = Image.new("RGB", (50, 50), color=(200, 50, 50))
    buf = io.BytesIO()
    dummy_img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode("ascii")

    multimodal_message = [
        {"type": "text", "text": "Please make this image clearer and professional."},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64_str,
            },
        },
    ]

    prompt_text, images = extract_image_payload(multimodal_message)
    assert "Please make this image clearer" in prompt_text
    assert len(images) == 1
    assert len(images[0]) > 0


def test_image_enhancer_local_clarity(tmp_path):
    """Verify ImageEnhancer processes input and generates a high-quality enhanced output."""
    # Create sample image with low contrast
    test_img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    enhancer = ImageEnhancer()

    enhanced_path, meta = enhancer.enhance_clarity(test_img, upscale_factor=1.5)
    assert enhanced_path.exists()
    assert enhanced_path.is_file()
    assert enhanced_path.stat().st_size > 0
    assert meta["new_size"] == "150x150"

    # Verify result image
    res_img = Image.open(enhanced_path)
    assert res_img.size[0] == 150
    assert res_img.size[1] == 150


def test_worker_enhancement_dispatch(qapp):
    """Verify ClaudeWorker intercepts image enhancement requests and produces the card."""
    dummy_img = Image.new("RGB", (60, 60), color=(120, 150, 180))
    buf = io.BytesIO()
    dummy_img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode("ascii")

    req = ChatRequest(
        message=[
            {"type": "text", "text": "pic aro clear and profestional kore dau"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64_str,
                },
            },
        ]
    )

    worker = ClaudeWorker()
    emitted_finished = []
    worker.finished.connect(lambda text: emitted_finished.append(text))

    worker.process(req)

    assert len(emitted_finished) == 1
    result_html = emitted_finished[0]
    assert "saveimage:" in result_html
    assert "Ultra-HD Portrait Clarity" in result_html
    assert "<img src=" in result_html
    assert "রেজোলিউশন আপস্কেল" in result_html
