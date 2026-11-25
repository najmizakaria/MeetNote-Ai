"""Draw the meeting mind map from short labels and export it as a crisp PNG."""
from __future__ import annotations

from functools import lru_cache
from math import cos, pi, sin
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .notes import MAX_MAP_BRANCHES


PNG_SIZE = 1800
CHARCOAL = "#333333"
ARROW = "#BBBBBB"
COLORS = ("#8EE8FF", "#C3FF73", "#FDF050", "#DDB5FF", "#FFBDE6", "#8EE8FF", "#FDF050", "#DDB5FF")
FONT_DIR = Path(__file__).with_name("fonts")
SYSTEM_FONTS = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


@lru_cache(maxsize=128)
def font_at(path: Path, size: int):
    return ImageFont.truetype(str(path), size)


def label_font(text: str, *, center: bool) -> Path:
    bundled = FONT_DIR / ("Poppins-SemiBold.ttf" if center else "Poppins-Medium.ttf")
    for path in (bundled, *(SYSTEM_FONTS / face for face in (
        "segoeui.ttf", "msyh.ttc", "YuGothM.ttc", "malgun.ttf", "Nirmala.ttc",
    ))):
        if path.is_file():
            font = font_at(path, 24)
            missing = bytes(font.getmask("\u0378"))
            if all(bytes(font.getmask(char)) != missing for char in set(text) if not char.isspace()):
                return path
    return bundled


def draw_label(draw, position, radius, text, *, center=False):
    font_path = label_font(text, center=center)
    size = 176 if center else 108
    font = font_at(font_path, size)
    width_limit, height_limit = radius * 1.66, radius * 1.05
    words = text.split()
    if len(words) > 1 and (center or font.getlength(text) > width_limit):
        lines = [(" ".join(words[:index]), " ".join(words[index:])) for index in range(1, len(words))]
        text = "\n".join(min(lines, key=lambda pair: max(map(font.getlength, pair))))

    spacing = size // 8
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    scale = min(1, width_limit / max(1, right - left), height_limit / max(1, bottom - top))
    if scale < 1:
        size = max(1, int(size * scale))
        font = font_at(font_path, size)
        spacing = size // 8
        left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    x, y = position
    draw.multiline_text((x - (left + right) / 2, y - (top + bottom) / 2), text,
                        fill="white" if center else CHARCOAL, font=font,
                        spacing=spacing, align="center")


def render_mind_map(topic: str, branches: list[str]) -> Image.Image:
    size = PNG_SIZE * 2
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    middle = size / 2
    hub, orbit, bubble = 480, 1180, 364
    branches = branches[:MAX_MAP_BRANCHES]
    centers = []
    for index in range(len(branches)):
        angle = -pi / 2 + index * 2 * pi / len(branches)
        dx, dy = cos(angle), sin(angle)
        x, y = middle + orbit * dx, middle + orbit * dy
        centers.append((x, y))
        tip = (x - (bubble + 25) * dx, y - (bubble + 25) * dy)
        base = (tip[0] - 34 * dx, tip[1] - 34 * dy)
        start = (middle + (hub + 25) * dx, middle + (hub + 25) * dy)
        draw.line((start, base), fill=ARROW, width=7)
        draw.polygon((tip, (base[0] - 13 * dy, base[1] + 13 * dx),
                      (base[0] + 13 * dy, base[1] - 13 * dx)), fill=ARROW)

    draw.ellipse((middle - hub, middle - hub, middle + hub, middle + hub), fill=CHARCOAL)
    draw_label(draw, (middle, middle), hub, topic, center=True)
    for index, ((x, y), text) in enumerate(zip(centers, branches)):
        draw.ellipse((x - bubble, y - bubble, x + bubble, y + bubble), fill=COLORS[index])
        draw_label(draw, (x, y), bubble, text)
    return image.resize((PNG_SIZE, PNG_SIZE), Image.Resampling.LANCZOS)
