"""Create a high-resolution 1024x1024 grid matching exact face positions and resolution."""

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

# UTF-8 stdout encoding for Windows
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
ORIGINAL_IMG_PATH = PROJECT_ROOT / "test.jpeg"
AGY_OUT_DIR = PROJECT_ROOT / "test_outputs" / "agy"
GRID_OUTPUT_PATH = AGY_OUT_DIR / "comparison_grid.png"

HAIRCUTS = [
    ("Original Selfie", ORIGINAL_IMG_PATH),
    ("Buzz Cut", AGY_OUT_DIR / "buzz_cut.png"),
    ("Classic Fade", AGY_OUT_DIR / "fade_classic.png"),
    ("Pompadour", AGY_OUT_DIR / "pompadour.png"),
    ("Undercut", AGY_OUT_DIR / "undercut.png"),
    ("French Crop", AGY_OUT_DIR / "french_crop.png"),
    ("Quiff", AGY_OUT_DIR / "quiff.png"),
    ("Curly Top", AGY_OUT_DIR / "curly_top.png"),
    ("Slick Back", AGY_OUT_DIR / "slick_back.png"),
    ("Modern Mullet", AGY_OUT_DIR / "modern_mullet.png"),
    ("Wolf Cut", AGY_OUT_DIR / "wolf_cut.png"),
    ("Afro", AGY_OUT_DIR / "afro.png"),
]


def create_comparison_grid():
    # 1024x1024 per cell for maximum high quality resolution!
    cell_size = 1024
    label_height = 90
    cols = 4
    rows = 3
    
    grid_w = cols * cell_size
    grid_h = rows * (cell_size + label_height)

    grid_img = Image.new("RGB", (grid_w, grid_h), color=(20, 20, 25))
    draw = ImageDraw.Draw(grid_img)

    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except Exception:
        font = ImageFont.load_default()

    for idx, (label, img_path) in enumerate(HAIRCUTS):
        r = idx // cols
        c = idx % cols
        x = c * cell_size
        y = r * (cell_size + label_height)

        if img_path.exists():
            raw_img = Image.open(img_path)
            raw_img = ImageOps.exif_transpose(raw_img).convert("RGB")
            
            if label == "Original Selfie":
                # The original image is a vertical portrait (e.g. 576x1024).
                # agy images are 1024x1024 square crops centered on the face with neck/shoulders.
                # To match agy outputs perfectly: center-crop the original from the top/middle (centering=(0.5, 0.45))
                fitted_img = ImageOps.fit(raw_img, (cell_size, cell_size), method=Image.LANCZOS, centering=(0.5, 0.45))
            else:
                fitted_img = raw_img.resize((cell_size, cell_size), Image.LANCZOS)
                
            grid_img.paste(fitted_img, (x, y))
        else:
            draw.rectangle([x, y, x + cell_size, y + cell_size], fill=(50, 50, 55))
            draw.text((x + 40, y + 40), f"Missing:\n{label}", fill=(200, 100, 100), font=font)

        # Label background bar
        lbl_bg_y1 = y + cell_size
        lbl_bg_y2 = lbl_bg_y1 + label_height
        draw.rectangle([x, lbl_bg_y1, x + cell_size, lbl_bg_y2], fill=(12, 12, 16))

        # Text centering
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x + (cell_size - text_w) // 2
        text_y = lbl_bg_y1 + (label_height - text_h) // 2
        draw.text((text_x, text_y), label, fill=(245, 245, 245), font=font)

    grid_img.save(GRID_OUTPUT_PATH, quality=98)
    print(f"High-quality comparison grid created successfully at: {GRID_OUTPUT_PATH}")


if __name__ == "__main__":
    create_comparison_grid()
