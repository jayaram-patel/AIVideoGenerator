"""
Local image renderer — generates cinematic scene images using Pillow.

Creates a high-quality 1920×1080 image for each scene by:
  1. Generating a mood-based gradient background
  2. Compositing the character reference image (soft-vignetted)
  3. Rendering the caption with professional typography and a text bar

Used when AI image generation models are unavailable/quota-exhausted.
"""

import hashlib
import logging
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# ── Output resolution ──────────────────────────────────────────────────────────
WIDTH = 1920
HEIGHT = 1080

# ── Colour palettes keyed by mood keywords in the visual prompt ────────────────
_PALETTES: list[tuple[list[str], tuple[int, int, int], tuple[int, int, int]]] = [
    # (keywords, colour_a, colour_b)
    (["sunrise", "dawn", "morning", "warm", "gold", "orange"],
     (20, 10, 5), (120, 50, 10)),
    (["sunset", "dusk", "evening", "amber"],
     (15, 5, 5), (100, 35, 10)),
    (["night", "dark", "shadow", "noir", "black"],
     (5, 5, 15), (15, 10, 35)),
    (["sky", "cloud", "aerial", "above", "heaven"],
     (10, 20, 40), (30, 60, 100)),
    (["forest", "nature", "green", "jungle", "tree"],
     (5, 15, 5), (20, 50, 20)),
    (["ocean", "sea", "water", "blue", "wave"],
     (5, 10, 25), (10, 40, 80)),
    (["fire", "flame", "passion", "red", "anger"],
     (20, 5, 5), (90, 20, 5)),
    (["hope", "success", "achieve", "victory", "triumph"],
     (10, 15, 30), (40, 80, 120)),
]

_DEFAULT_PALETTE = ((10, 10, 20), (40, 40, 80))


def _pick_palette(prompt: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    low = prompt.lower()
    for keywords, ca, cb in _PALETTES:
        if any(kw in low for kw in keywords):
            return ca, cb
    # Deterministic fallback based on prompt hash so each scene looks different
    h = int(hashlib.md5(prompt.encode()).hexdigest(), 16)
    idx = h % len(_PALETTES)
    return _PALETTES[idx][1], _PALETTES[idx][2]


def _make_gradient(width: int, height: int,
                   top: tuple[int, int, int],
                   bottom: tuple[int, int, int]) -> Image.Image:
    """Create a smooth vertical gradient."""
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        t = y / (height - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def _add_vignette(img: Image.Image) -> Image.Image:
    """Darken edges for a cinematic look."""
    w, h = img.size
    vignette = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(vignette)
    cx, cy = w // 2, h // 2
    steps = 60
    for i in range(steps, 0, -1):
        alpha = int(180 * (1 - i / steps) ** 2)
        rx = int(cx * i / steps)
        ry = int(cy * i / steps)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=80))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = Image.composite(img, dark, vignette)
    return img


def _composite_character(canvas: Image.Image, char_path: Path) -> Image.Image:
    """
    Paste the character reference image centred on the canvas.

    The character image is scaled to fill ~60% of the canvas height,
    horizontally centred at 35% from the left, and softly feathered
    at the edges so it blends into the gradient.
    """
    try:
        char = Image.open(char_path).convert("RGBA")
    except Exception:
        return canvas

    cw, ch = canvas.size
    target_h = int(ch * 0.78)
    ratio = target_h / char.height
    target_w = int(char.width * ratio)
    char = char.resize((target_w, target_h), Image.LANCZOS)

    # Build a soft circular/elliptical mask
    mask = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(mask)
    mx, my = target_w // 2, target_h // 2
    rx, ry = int(mx * 0.9), int(my * 0.97)
    draw.ellipse([mx - rx, my - ry, mx + rx, my + ry], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=min(target_w, target_h) // 8))

    # Position: horizontally centred, vertically bottom-aligned
    paste_x = (cw - target_w) // 2
    paste_y = ch - target_h - 10

    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(char, (paste_x, paste_y), mask)
    return canvas_rgba.convert("RGB")


def _render_caption(canvas: Image.Image, caption: str, scene_num: int) -> Image.Image:
    """
    Render a professional caption bar at the bottom of the image.

    Layout:
      ┌──────────────────────────────────────────┐
      │  ████  CAPTION TEXT  ░░░░░░░░░░░░░░░░░  │  ← frosted bar
      └──────────────────────────────────────────┘
    """
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size

    # ── Semi-transparent bottom bar ──
    bar_h = int(h * 0.14)
    bar_y = h - bar_h
    overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle([0, 0, w, bar_h], fill=(0, 0, 0, 180))
    # Accent line at the top of the bar
    odraw.rectangle([0, 0, w, 4], fill=(255, 200, 50, 220))
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(overlay, (0, bar_y), overlay)
    canvas = canvas_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # ── Caption text ──
    font_size = int(bar_h * 0.42)
    font = _load_font(font_size)
    # Word-wrap if too wide
    max_w = int(w * 0.82)
    lines = _wrap_text(caption.upper(), font, max_w, draw)
    line_h = font_size + 6
    total_text_h = len(lines) * line_h
    text_y = bar_y + (bar_h - total_text_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        tx = (w - text_w) // 2
        ty = text_y + i * line_h
        # Shadow
        draw.text((tx + 2, ty + 2), line, fill=(0, 0, 0), font=font)
        # Main text
        draw.text((tx, ty), line, fill=(255, 255, 255), font=font)

    # ── Scene number badge ──
    badge_font = _load_font(int(bar_h * 0.28))
    badge_text = f"SCENE {scene_num:02d}"
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = badge_bbox[2] - badge_bbox[0]
    bx = w - badge_w - 40
    by = bar_y + (bar_h - (badge_bbox[3] - badge_bbox[1])) // 2
    draw.text((bx, by), badge_text, fill=(180, 180, 180), font=badge_font)

    return canvas


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a system font, fall back to default."""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int,
               draw: ImageDraw.ImageDraw) -> list[str]:
    """Break text into lines that fit within max_width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _add_film_grain(img: Image.Image, intensity: float = 0.03) -> Image.Image:
    """Add subtle film grain for a cinematic feel."""
    import random
    grain = Image.new("RGB", img.size)
    pixels = grain.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            v = int(random.gauss(128, 20 * intensity * 255))
            v = max(0, min(255, v))
            pixels[x, y] = (v, v, v)  # type: ignore[index]
    grain = grain.filter(ImageFilter.GaussianBlur(radius=0.5))
    return Image.blend(img, grain, intensity * 0.3)


def render_scene_image(
    visual_prompt: str,
    caption: str,
    scene_num: int,
    character_image_path: Path,
    output_path: Path,
) -> Path:
    """
    Generate a cinematic scene image locally using Pillow.

    Returns the output path after saving the PNG.
    """
    logger.info("Rendering scene %d locally: %s", scene_num, caption[:50])

    # 1. Gradient background
    col_top, col_bottom = _pick_palette(visual_prompt)
    canvas = _make_gradient(WIDTH, HEIGHT, col_top, col_bottom)

    # 2. Vignette overlay
    canvas = _add_vignette(canvas)

    # 3. Character reference
    canvas = _composite_character(canvas, character_image_path)

    # 4. Caption bar
    canvas = _render_caption(canvas, caption, scene_num)

    # 5. Subtle film grain
    canvas = _add_film_grain(canvas, intensity=0.015)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path), "PNG", optimize=False)
    logger.info("Scene %d saved → %s (%d KB)",
                scene_num, output_path.name, output_path.stat().st_size // 1024)
    return output_path
