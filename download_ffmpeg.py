"""Download and setup script for FFmpeg binaries in Jakariya AI Studio.

Downloads FFmpeg zip from official release channels and extracts binaries locally
without committing large 24MB+ zip archives to Git.
"""

import argparse
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

# Primary official FFmpeg Windows 64-bit release URL
DEFAULT_FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
# Mirror URL fallback
FALLBACK_FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file from a URL to dest_path with progress feedback."""
    print(f"Downloading FFmpeg from: {url}")
    try:
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100.0, (downloaded / total_size) * 100.0)
                mb_dn = downloaded / (1024 * 1024)
                mb_tot = total_size / (1024 * 1024)
                sys.stdout.write(f"\rProgress: {percent:.1f}% ({mb_dn:.1f} MB / {mb_tot:.1f} MB)")
                sys.stdout.flush()

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
            block_size = 8192
            total_size = int(response.headers.get("Content-Length", 0))
            block_num = 0
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                out_file.write(buffer)
                block_num += 1
                progress_hook(block_num, block_size, total_size)
        print("\nDownload complete!")
        return True
    except Exception as exc:
        print(f"\nFailed download from {url}: {exc}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def extract_ffmpeg(zip_path: Path, output_dir: Path) -> bool:
    """Extract ffmpeg.exe and ffprobe.exe into output_dir."""
    print(f"Extracting binaries from {zip_path.name} into {output_dir}...")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted_count = 0
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if filename.lower() in ("ffmpeg.exe", "ffprobe.exe", "ffmpeg", "ffprobe"):
                    target_file = output_dir / filename
                    with zip_ref.open(member) as source, open(target_file, "wb") as target:
                        target.write(source.read())
                    print(f"  Extracted: {target_file}")
                    extracted_count += 1

        if extracted_count > 0:
            print(f"Successfully extracted {extracted_count} FFmpeg binary file(s).")
            return True
        else:
            print("Warning: No matching ffmpeg executable files found in archive.")
            return False
    except Exception as exc:
        print(f"Error during archive extraction: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and setup FFmpeg binaries locally.")
    parser.add_argument("--output-dir", type=str, default="assets/bin", help="Target output directory for binaries")
    parser.add_argument("--url", type=str, default=DEFAULT_FFMPEG_URL, help="Custom download URL for FFmpeg zip archive")
    parser.add_argument("--keep-zip", action="store_true", help="Retain downloaded zip archive after extraction")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    output_dir = project_root / args.output_dir
    zip_path = project_root / "ffmpeg.zip"

    if not zip_path.exists():
        success = download_file(args.url, zip_path)
        if not success and args.url == DEFAULT_FFMPEG_URL:
            print(f"Retrying download with mirror URL: {FALLBACK_FFMPEG_URL}")
            success = download_file(FALLBACK_FFMPEG_URL, zip_path)
        if not success:
            print("Error: Failed to obtain FFmpeg archive.")
            sys.exit(1)

    extract_success = extract_ffmpeg(zip_path, output_dir)

    if not args.keep_zip and zip_path.exists():
        print("Cleaning up temporary zip archive...")
        zip_path.unlink()

    if extract_success:
        print("\nFFmpeg setup completed successfully!")
    else:
        print("\nFFmpeg setup completed with warnings.")


if __name__ == "__main__":
    main()
