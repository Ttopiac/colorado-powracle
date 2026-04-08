"""Render the three mermaid diagrams in architecture.md to PNG via mermaid.ink."""
import base64, zlib, json, re, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
ARCH = (ROOT / "architecture.md").read_text()
OUT = ROOT / "slides" / "assets"
OUT.mkdir(exist_ok=True)

# Pull all mermaid blocks in order
blocks = re.findall(r"```mermaid\n(.*?)```", ARCH, re.DOTALL)
names = ["simple_overview.png", "detailed_architecture.png", "evaluation_harness.png"]
assert len(blocks) >= 3, f"expected 3 mermaid blocks, found {len(blocks)}"

def render(src: str, out: Path):
    # mermaid.ink pako format
    payload = {"code": src, "mermaid": {"theme": "default"}}
    data = json.dumps(payload).encode()
    compressed = zlib.compress(data, 9)
    b64 = base64.urlsafe_b64encode(compressed).decode().rstrip("=")
    url = f"https://mermaid.ink/img/pako:{b64}?type=png"
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        # fallback: plain base64
        b64 = base64.urlsafe_b64encode(src.encode()).decode().rstrip("=")
        url = f"https://mermaid.ink/img/{b64}?type=png"
        r = requests.get(url, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"  wrote {out.name} ({len(r.content)} bytes)")

for src, name in zip(blocks[:3], names):
    print(f"rendering {name}...")
    render(src, OUT / name)

print("done.")
