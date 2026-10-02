#!/usr/bin/env python3
"""Generate 1200x630 PNG social cards (static/og/*.png) from post front matter.

Usage:  python3 scripts/make-og.py            # all posts + default card
        python3 scripts/make-og.py <slug>...  # only these posts

Needs a headless Chrome/Chromium (CHROME env var, else common paths). Output is committed because
CI does not render images. Card design mirrors assets/css/main.css (dark, orange/green accents).
"""
import html, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "og"
CHROME = next((c for c in [os.environ.get("CHROME"),
                           str(Path.home() / ".hermes/tools/chromium-1208/chrome-linux64/chrome"),
                           shutil.which("chromium"), shutil.which("google-chrome"), shutil.which("chrome")]
               if c and Path(c).exists()), None)

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or str(Path.home() / ".hermes/tools/ffmpeg-9.0.1-linux-x64/ffmpeg")

CSS = """
*{box-sizing:border-box;margin:0}
body{width:1200px;height:630px;background:#0a0d0c;color:#e9eee9;font-family:'DejaVu Sans',Inter,Arial,sans-serif;
 position:relative;overflow:hidden}
.glow1{position:absolute;right:-120px;top:-150px;width:560px;height:560px;border-radius:50%;background:#f0a33a;opacity:.09}
.glow2{position:absolute;left:-160px;bottom:-200px;width:600px;height:600px;border-radius:50%;background:#9ecf63;opacity:.07}
.frame{position:absolute;inset:18px;border:1px solid #2b3530}
.top{position:absolute;left:70px;top:58px;display:flex;align-items:center;gap:18px}
.mark{width:54px;height:54px;border:1px solid #435047;background:#151b18;color:#f0a33a;display:grid;place-items:center;
 font:800 19px/1 'DejaVu Sans Mono',monospace;letter-spacing:-2px;box-shadow:6px 6px 0 #3a2916}
.brand{font:700 22px 'DejaVu Sans Mono',monospace;letter-spacing:3px;color:#9ecf63;text-transform:uppercase}
.title{position:absolute;left:70px;right:70px;top:150px;font-weight:800;letter-spacing:-1.5px;line-height:1.08}
.title em{color:#f0a33a;font-style:normal}
.desc{position:absolute;left:70px;right:90px;bottom:128px;color:#9ba79f;font-size:24px;line-height:1.4}
.tags{position:absolute;left:70px;bottom:62px;display:flex;gap:12px}
.tag{font:600 17px 'DejaVu Sans Mono',monospace;color:#9ecf63;border:1px solid #1d2d19;background:#1d2d19;padding:6px 12px}
.meta{position:absolute;right:70px;bottom:66px;font:600 18px 'DejaVu Sans Mono',monospace;color:#68736c}
.bar{position:absolute;left:70px;bottom:36px;height:5px;width:170px;background:#f0a33a}
.bar2{position:absolute;left:250px;bottom:36px;height:5px;width:65px;background:#9ecf63}
"""

def front(p):
    t = p.read_text()
    m = re.match(r"---\n(.*?)\n---", t, re.S)
    fm = m.group(1)
    g = lambda k: (re.search(rf'^{k}:\s*"?(.*?)"?\s*$', fm, re.M) or [None, ""])[1]
    tags = re.findall(r'"([^"]+)"', (re.search(r"^tags:\s*\[(.*)\]", fm, re.M) or [None, ""])[1])
    return dict(title=g("title").replace('\\"', '"'), desc=g("description").replace('\\"', '"'),
                date=g("date")[:10], draft=g("draft") == "true", tags=tags)

def card(title, desc, tags, meta, emphasis=None):
    n = len(title)
    size = 78 if n < 38 else 62 if n < 70 else 52 if n < 100 else 46
    t = html.escape(title)
    if emphasis and emphasis in title:
        t = html.escape(title).replace(html.escape(emphasis), f"<em>{html.escape(emphasis)}</em>", 1)
    if len(desc) > 150:
        desc = desc[:147].rsplit(" ", 1)[0] + "…"
    tag_html = "".join(f'<span class="tag">{html.escape(x)}</span>' for x in tags[:4])
    return f"""<!doctype html><meta charset=utf-8><style>{CSS}</style><body>
<div class=glow1></div><div class=glow2></div><div class=frame></div>
<div class=top><div class=mark>P/R</div><div class=brand>Packets &amp; Regrets</div></div>
<div class=title style="font-size:{size}px">{t}</div>
<div class=desc>{html.escape(desc)}</div>
<div class=tags>{tag_html}</div><div class=meta>{html.escape(meta)}</div>
<div class=bar></div><div class=bar2></div></body>"""

def shot(html_str, out):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html_str)
    try:
        subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--window-size=1200,717",
                        f"--screenshot={out}.raw.png", f"file://{f.name}"], check=True, capture_output=True, timeout=60)
        # headless=new gives a viewport 87px shorter than the window, so render tall and crop to exactly 1200x630
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", f"{out}.raw.png", "-vf", "crop=1200:630:0:0",
                        "-frames:v", "1", str(out)], check=True, capture_output=True, timeout=60)
        os.unlink(f"{out}.raw.png")
    finally:
        os.unlink(f.name)

def main():
    if not CHROME:
        sys.exit("no Chrome/Chromium found (set CHROME=/path/to/chrome)")
    OUT.mkdir(parents=True, exist_ok=True)
    want = set(sys.argv[1:])
    if not want:
        shot(card("Packets & Regrets", "Field notes from a SecOps engineer running production habits at home: "
                  "architecture, incidents, security trade-offs, and the occasional regrettable shortcut.",
                  ["Homelab", "SecOps", "Observability"], "blog.zezelj.org", "Regrets"), ROOT / "static" / "og-default.png")
        print("og-default.png")
    for p in sorted((ROOT / "content" / "posts").glob("*.md")):
        if p.name.startswith("_") or (want and p.stem not in want):
            continue
        f = front(p)
        if f["draft"] and not want:   # naming a slug explicitly renders its card even while it is still a draft
            continue
        shot(card(f["title"], f["desc"], f["tags"], f["date"]), OUT / f"{p.stem}.png")
        print(f"og/{p.stem}.png")

if __name__ == "__main__":
    main()
