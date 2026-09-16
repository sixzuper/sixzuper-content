#!/usr/bin/env python3
"""Render a premium 1080x1350 SixZuper educational IG card.

Use image-generation output as a text-free background; render all readable text
locally for consistent typography and brand safety.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
ROOT = Path(__file__).resolve().parents[1]
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def wrap(text: str, fontobj, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    """Word-wrap multiline text to fit inside max_width (pixels)."""
    import textwrap
    lines_out = []
    for raw_line in text.split("\n"):
        wrapped = textwrap.wrap(raw_line, width=120, break_long_words=False, break_on_hyphens=True)
        if not wrapped:
            lines_out.append("")
            continue
        for w in wrapped:
            # measure iteratively; reduce if needed
            while draw.textlength(w, font=fontobj) > max_width and len(w.split()) > 1:
                w = " ".join(w.split()[:-1])
            lines_out.append(w)
    return "\n".join(lines_out)


def rounded(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def fit_bg(source: Path) -> Image.Image:
    img = Image.open(source).convert("RGB")
    scale = max(W / img.width, H / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - W) // 2
    top = (resized.height - H) // 2
    return resized.crop((left, top, left + W, top + H)).convert("RGBA")


def gradient_overlay() -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = layer.load()
    for x in range(W):
        # Dense reading zone on the left; fades into generated image.
        t = min(1.0, x / 720)
        alpha = int(238 * (1 - t) ** 1.7)
        for y in range(H):
            vertical = 18 if y < 270 or y > 1070 else 0
            px[x, y] = (3, 8, 23, min(255, alpha + vertical))
    return layer


def draw_card(source: Path, output: Path, title: str = "", body: str = "") -> None:
    canvas = fit_bg(source)
    canvas.alpha_composite(gradient_overlay())
    draw = ImageDraw.Draw(canvas)

    cyan = (0, 212, 255, 255)
    white = (244, 249, 255, 255)
    muted = (165, 186, 209, 255)
    violet = (142, 84, 255, 255)
    dark = (5, 13, 34, 220)

    # Top rule and brand marker
    draw.line((72, 74, 1008, 74), fill=(38, 85, 125, 180), width=2)
    rounded(draw, (72, 108, 318, 158), 25, fill=(5, 25, 48, 235), outline=cyan, width=2)
    draw.text((96, 119), "SIXZUPER  /  LABS", font=font(BOLD, 19), fill=cyan)
    draw.text((72, 188), "EDUCATIONAL CARD", font=font(BOLD, 22), fill=muted)

    # Main headline (dynamic title)
    title_lines = wrap(title if title else "REST API", font(BOLD, 83), 900, draw).split("\n")[:2]
    if not title:
        title_lines = ["REST API", "Error Format"]
    draw.text((72, 242), title_lines[0], font=font(BOLD, 83), fill=white)
    if len(title_lines) > 1:
        draw.text((72, 334), title_lines[1], font=font(BOLD, 83), fill=white)
    draw.rounded_rectangle((72, 448, 234, 456), radius=4, fill=cyan)

    # Supporting message (dynamic body)
    body_wrapped = wrap(body if body else "Gunakan HTTP status code yang tepat untuk API yang predictable.", font(REGULAR, 35), 900, draw)
    draw.multiline_text((72, 490), body_wrapped, font=font(REGULAR, 35), fill=(222, 236, 249, 255), spacing=12)

    # Status chips
    chips = [("200", "SUCCESS", cyan), ("404", "NOT FOUND", violet), ("429", "RATE LIMIT", (255, 180, 61, 255))]
    y = 738
    x = 72
    for code, label, accent in chips:
        width = 214 if code != "404" else 234
        rounded(draw, (x, y, x + width, y + 74), 18, fill=dark, outline=(73, 108, 149, 170), width=1)
        draw.text((x + 20, y + 15), code, font=font(BOLD, 28), fill=accent)
        draw.text((x + 86, y + 25), label, font=font(BOLD, 13), fill=muted)
        x += width + 14

    # Bottom CTA panel
    rounded(draw, (72, 1138, 1008, 1262), 26, fill=(5, 14, 35, 220), outline=(32, 102, 158, 155), width=2)
    draw.text((104, 1163), "Build API yang predictable.", font=font(BOLD, 27), fill=white)
    draw.text((104, 1204), "Simpan post ini untuk referensi.", font=font(REGULAR, 21), fill=muted)
    draw.ellipse((910, 1172, 956, 1218), fill=(5, 25, 48, 240), outline=cyan, width=2)
    # Vector arrow: avoids font glyph fallback in exported cards.
    draw.line((922, 1195, 944, 1195), fill=cyan, width=3)
    draw.line((938, 1188, 945, 1195), fill=cyan, width=3)
    draw.line((938, 1202, 945, 1195), fill=cyan, width=3)

    # Footer
    draw.text((72, 1292), "sixzuper  •  practical AI & tech workflow", font=font(REGULAR, 16), fill=(114, 148, 181, 255))
    canvas.convert("RGB").save(output, "PNG", optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--background", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--body", default="")
    args = ap.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    draw_card(Path(args.background), output, args.title, args.body)
    print(output)


if __name__ == "__main__":
    main()
