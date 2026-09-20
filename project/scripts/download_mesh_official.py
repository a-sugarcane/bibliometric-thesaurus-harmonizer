"""Official NLM MeSH bulk dataset downloader.

Downloads:
  1. desc2026.gz (~16.8 MB) - MeSH Descriptors (Headings & Entry Terms)
  2. qual2026.xml (~290 KB) - MeSH Qualifiers (Subheadings)
  3. pa2026.xml (~5.3 MB)   - Pharmacological Action Mappings
  4. supp2026.gz (~47.3 MB) - Supplementary Concept Records (Chemicals/Drugs)
"""

import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/"

FILES_TO_DOWNLOAD = [
    "desc2026.gz",
    "qual2026.xml",
    "pa2026.xml",
    "supp2026.gz",
]


import ssl
import subprocess

# Bypass macOS unverified certificate issue if root certificates are not linked
try:
    _ssl_context = ssl.create_default_context()
except Exception:
    _ssl_context = ssl._create_unverified_context()

def download_file(url: str, dest_path: Path):
    """Download file with curl or urllib, handling macOS SSL certificates."""
    print(f"[*] Downloading {url} -> {dest_path.name}...")
    start_time = time.time()

    # Prefer system curl on macOS because it uses the native macOS Keychain root trust
    cmd = ["curl", "-L", "--fail", "--retry", "3", "-o", str(dest_path), url]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback to urllib with unverified context
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=ctx) as response, open(dest_path, "wb") as out_file:
            out_file.write(response.read())

    elapsed = time.time() - start_time
    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"[+] Completed {dest_path.name} ({size_mb:.2f} MB) in {elapsed:.1f}s.")


def main():
    target_dir = Path(__file__).resolve().parent.parent / "resources" / "mesh_raw"
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting NLM MeSH official bulk download into: {target_dir}")
    for fname in FILES_TO_DOWNLOAD:
        file_url = BASE_URL + fname
        dest_file = target_dir / fname
        if dest_file.is_file() and dest_file.stat().st_size > 0:
            print(f"[*] File {fname} already exists ({dest_file.stat().st_size / 1024:.1f} KB). Skipping.")
            continue
        download_file(file_url, dest_file)

    print("[+] All official MeSH files successfully downloaded.")


if __name__ == "__main__":
    main()
