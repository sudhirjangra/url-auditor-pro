"""
generate_icon.py — run before PyInstaller to produce logo.ico
Requires: pillow

Usage:  python generate_icon.py
Output: logo.ico  (multi-size: 16,32,48,64,128,256)
"""

import io
import math
import struct
from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── background: rounded square with deep blue-to-teal gradient simulation ──
    pad = max(1, size // 16)
    r   = size // 5  # corner radius

    # layered gradient: draw concentric rounded rects from dark → light
    steps = max(12, size // 8)
    for i in range(steps):
        t     = i / steps
        # #0d1b2a → #1a6b8a (deep navy to teal)
        red   = int(13  + (26  - 13)  * t)
        green = int(27  + (107 - 27)  * t)
        blue  = int(42  + (138 - 42)  * t)
        inset = int(pad + (size * 0.25) * (1 - t))
        d.rounded_rectangle(
            [inset, inset, size - inset, size - inset],
            radius=max(2, r - inset // 2),
            fill=(red, green, blue, 255),
        )

    # ── background rounded rect final clean fill (deep navy) ──────────────────
    # already drawn via gradient above; add a subtle border glow
    border_c = (0, 200, 200, 160)
    d.rounded_rectangle([pad, pad, size - pad, size - pad],
                        radius=r, outline=border_c,
                        width=max(1, size // 48))

    # ── magnifying glass body ──────────────────────────────────────────────────
    cx  = size * 0.42
    cy  = size * 0.41
    or_ = size * 0.23   # outer radius
    ir_ = size * 0.16   # inner radius (hollow)
    ring_w = max(2, size // 20)

    # outer glow ring (cyan accent)
    glow_r = or_ + size // 16
    d.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r],
              fill=(0, 220, 220, 50))

    # main ring — white with subtle alpha
    d.ellipse([cx - or_, cy - or_, cx + or_, cy + or_],
              fill=(255, 255, 255, 240))
    d.ellipse([cx - ir_, cy - ir_, cx + ir_, cy + ir_],
              fill=(0, 0, 0, 0))   # punch hole

    # inner glass tint (semi-transparent cyan)
    d.ellipse([cx - ir_, cy - ir_, cx + ir_, cy + ir_],
              fill=(0, 180, 200, 60))

    # ── handle ────────────────────────────────────────────────────────────────
    angle = math.radians(45)
    hx1 = cx + ir_ * 0.7 * math.cos(angle)
    hy1 = cy + ir_ * 0.7 * math.sin(angle)
    hx2 = cx + (or_ + size * 0.22) * math.cos(angle)
    hy2 = cy + (or_ + size * 0.22) * math.sin(angle)
    hw  = max(2, size // 12)

    # handle shadow
    d.line([hx1 + 1, hy1 + 1, hx2 + 1, hy2 + 1],
           fill=(0, 0, 0, 120), width=hw + 2)
    # handle main
    d.line([hx1, hy1, hx2, hy2],
           fill=(255, 255, 255, 230), width=hw)
    # handle rounded tip
    tip_r = hw // 2
    d.ellipse([hx2 - tip_r, hy2 - tip_r, hx2 + tip_r, hy2 + tip_r],
              fill=(200, 240, 255, 230))

    # ── link / check mark accent inside lens ──────────────────────────────────
    # small "✓" tick rendered as lines at sufficient size
    if size >= 48:
        tk = size * 0.065
        tx, ty = cx - tk * 0.6, cy + tk * 0.1
        # tick stroke 1
        d.line([tx - tk, ty, tx, ty + tk],
               fill=(0, 220, 180, 255), width=max(1, size // 32))
        # tick stroke 2
        d.line([tx, ty + tk, tx + tk * 1.6, ty - tk * 1.2],
               fill=(0, 220, 180, 255), width=max(1, size // 32))

    # ── tiny dot accent (top-right of lens) ───────────────────────────────────
    dot_r = max(1, size // 28)
    dot_x = cx + ir_ * 0.55
    dot_y = cy - ir_ * 0.6
    d.ellipse([dot_x - dot_r, dot_y - dot_r,
               dot_x + dot_r, dot_y + dot_r],
              fill=(180, 255, 240, 200))

    return img


def generate(out_path: str = "logo.ico"):
    sizes   = [16, 32, 48, 64, 128, 256]
    entries = []
    for s in sizes:
        buf = io.BytesIO()
        draw_icon(s).convert("RGBA").save(buf, format="PNG")
        entries.append((s, buf.getvalue()))

    # Build ICO manually — Pillow's .save(format="ICO") only writes first frame
    n           = len(entries)
    header_size = 6 + n * 16
    offset      = header_size
    dir_entries = b""
    image_data  = b""
    for s, data in entries:
        w = 0 if s == 256 else s   # 0 means 256 in ICO spec
        h = 0 if s == 256 else s
        dir_entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        image_data  += data
        offset      += len(data)

    ico_header = struct.pack("<HHH", 0, 1, n)
    with open(out_path, "wb") as f:
        f.write(ico_header + dir_entries + image_data)

    print(f"Saved {out_path}  ({', '.join(str(s) for s in sizes)}px)")


if __name__ == "__main__":
    generate()
