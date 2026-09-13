"""Генерація іконки програми assets/app.ico.

Малюнок: кіноплівка з помаранчевим знаком «відтворити» на темно-синьому тлі.
Потрібен Pillow:  python -m pip install pillow

    python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BG = (27, 42, 74, 255)          # темно-синій
FILM = (238, 240, 245, 255)     # світла плівка
ACCENT = (255, 145, 30, 255)    # помаранчевий трикутник
ACCENT_EDGE = (140, 70, 0, 255)

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18), fill=BG)

    band_top, band_bottom = int(size * 0.26), int(size * 0.74)
    d.rectangle([0, band_top, size, band_bottom], fill=FILM)

    # перфорація плівки
    hole_w, hole_h = int(size * 0.075), int(size * 0.055)
    gap = int(size * 0.038)
    top_y = band_top + int(size * 0.018)
    bottom_y = band_bottom - int(size * 0.018) - hole_h
    radius = max(1, int(hole_w * 0.28))
    x = gap
    while x + hole_w < size:
        d.rounded_rectangle([x, top_y, x + hole_w, top_y + hole_h], radius=radius, fill=BG)
        d.rounded_rectangle([x, bottom_y, x + hole_w, bottom_y + hole_h], radius=radius, fill=BG)
        x += hole_w + gap

    # знак «відтворити»
    cx, cy = size / 2, size / 2
    half = size * 0.185
    triangle = [(cx - half * 0.8, cy - half), (cx - half * 0.8, cy + half), (cx + half, cy)]
    d.polygon(triangle, fill=ACCENT)
    d.line(triangle + [triangle[0]], fill=ACCENT_EDGE, width=max(1, int(size * 0.012)), joint="curve")
    return img


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    master = draw_icon(1024)
    frames = [master.resize(s, Image.LANCZOS) for s in SIZES]
    ico = ASSETS / "app.ico"
    frames[-1].save(ico, format="ICO", sizes=SIZES, append_images=frames[:-1])
    master.resize((256, 256), Image.LANCZOS).save(ASSETS / "app.png")
    print(f"Готово: {ico}")


if __name__ == "__main__":
    main()
