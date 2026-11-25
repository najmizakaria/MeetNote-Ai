from math import cos, pi, sin

from PIL import ImageColor

from meetnote.mind_map import COLORS, PNG_SIZE, render_mind_map
from meetnote.notes import clean_mind_map


def test_radial_template_preserves_exact_colors_and_adapts_to_branch_count():
    for labels in (["Topic A", "Topic B", "Topic C"], ["Topic"] * 8):
        diagram = render_mind_map("Smart City", labels)
        assert diagram.size == (PNG_SIZE, PNG_SIZE)
        assert diagram.getpixel((70, 70)) == (255, 255, 255)
        assert diagram.getpixel((900, 1050)) == (51, 51, 51)
        for index in range(len(labels)):
            angle = -pi / 2 + index * 2 * pi / len(labels)
            pixel = (round(900 + 590 * cos(angle)), round(900 + 590 * sin(angle) + 90))
            assert diagram.getpixel(pixel) == ImageColor.getrgb(COLORS[index])


def test_map_labels_are_unique_and_limited_to_eight():
    result = clean_mind_map({"topic": " Testing ", "branches": ["testing.", "Demo", " demo ",
                                                             None, *map(str, range(12))]})
    assert result["branches"] == ["Demo", *map(str, range(7))]
