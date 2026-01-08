import os
from typing import List
from PIL import Image, ImageDraw, ImageFont
import yaml


def _load_grid_cols(config_path: str) -> int:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return int(cfg.get("video", {}).get("grid_cols", 4))


def _annotate_cell_top(draw: ImageDraw.ImageDraw, cell_bbox, color=(255, 0, 0), thickness=6, band_ratio=0.18):
    x0, y0, x1, y1 = cell_bbox
    band_h = int((y1 - y0) * band_ratio)
    # top band rectangle (filled with transparent red overlay effect by drawing border multiple times)
    for t in range(thickness):
        draw.rectangle([x0 + t, y0 + t, x1 - t, y0 + band_h - t], outline=color, width=1)


def _draw_label(draw: ImageDraw.ImageDraw, text: str, xy, color=(255, 0, 0)):
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text(xy, text, fill=color, font=font)


def annotate_images(image_paths: List[str], output_dir: str, config_path: str):
    os.makedirs(output_dir, exist_ok=True)
    grid_cols = _load_grid_cols(config_path)

    for img_path in image_paths:
        img = Image.open(img_path).convert("RGB")
        W, H = img.size

        cell_w = W // grid_cols
        # assume square layout (rows == cols); for last grid may be fewer rows, but these targets are full grids
        grid_rows = grid_cols
        cell_h = H // grid_rows

        draw = ImageDraw.Draw(img)

        # Assume occurrence is in row 2, col 1 (0-indexed row=1, col=0)
        target_cells = [(1, 0)]
        for r, c in target_cells:
            x0 = c * cell_w
            y0 = r * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            _annotate_cell_top(draw, (x0, y0, x1, y1))
            _draw_label(draw, "Widgetsmith", (x0 + 12, y0 + 12))

        basename = os.path.basename(img_path)
        out_path = os.path.join(output_dir, basename.replace(".jpg", "_marked.jpg"))
        img.save(out_path, "JPEG", quality=92)


if __name__ == "__main__":
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base, "config.yaml")
    targets = [
        os.path.join(base, "screenshots", "3_grids", "3_10_36.0s_39.8s.jpg"),
        os.path.join(base, "screenshots", "3_grids", "3_11_40.0s_43.5s.jpg"),
    ]
    output_dir = os.path.join(base, "screenshots", "3_grids_marked")
    annotate_images(targets, output_dir, config_path)

