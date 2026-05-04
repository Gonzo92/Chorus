# ============================================================
#  Chorus v2.2  –  tools/generate_icon.py
#  Generates a satellite dish icon (Chorus.ico) programmatically.
#  Run: python tools/generate_icon.py
# ============================================================

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont


def generate_satellite_dish_icon(output_path: str, size: int = 256) -> None:
    """Generate a satellite dish icon and save as .ico with multiple sizes."""
    # ── colors ───────────────────────────────────────────────
    BG = (15, 17, 23)          # dark background (#0f1117)
    DISH_COLOR = (109, 170, 255)  # bright blue (#6daaff)
    DISH_HIGHLIGHT = (150, 200, 255)  # lighter blue for 3D effect
    ARM_COLOR = (109, 170, 255)
    FEED_COLOR = (90, 160, 240)
    POLE_COLOR = (80, 130, 200)
    WAVE_COLOR = (109, 170, 255)
    WAVE_ALPHA = 80            # transparency for waves

    # ── create base image ────────────────────────────────────
    img = Image.new("RGBA", (size, size), (*BG, 0))
    draw = ImageDraw.Draw(img)

    cx = size // 2
    cy = size // 2
    scale = size / 256

    # ── 1. Dish (parabolic bowl) ─────────────────────────────
    # Draw the dish as an ellipse tilted to look 3D
    dish_width = int(160 * scale)
    dish_height = int(100 * scale)
    dish_x1 = cx - dish_width // 2
    dish_y1 = cy - dish_height // 2 - int(10 * scale)
    dish_x2 = cx + dish_width // 2
    dish_y2 = cy + dish_height // 2 - int(10 * scale)

    # Dish outer rim (darker)
    draw.ellipse([dish_x1 - 2, dish_y1 - 2, dish_x2 + 2, dish_y2 + 2],
                 fill=POLE_COLOR, outline=POLE_COLOR)

    # Dish inner (main bowl)
    draw.ellipse([dish_x1, dish_y1, dish_x2, dish_y2],
                 fill=DISH_COLOR)

    # Dish highlight (top-left gradient effect)
    highlight_x1 = dish_x1 + int(15 * scale)
    highlight_y1 = dish_y1 + int(10 * scale)
    highlight_x2 = cx + int(20 * scale)
    highlight_y2 = cy - int(10 * scale)
    draw.ellipse([highlight_x1, highlight_y1, highlight_x2, highlight_y2],
                 fill=DISH_HIGHLIGHT)

    # ── 2. Signal waves (emanating from dish top) ────────────
    wave_y = dish_y1 - int(5 * scale)
    for i, wave_width in enumerate([dish_width - 20, dish_width - 60, dish_width - 100]):
        wave_alpha = max(0, WAVE_ALPHA - i * 25)
        wave_color = (*WAVE_COLOR, wave_alpha)
        wave_x1 = cx - wave_width // 2
        wave_x2 = cx + wave_width // 2
        wave_y1 = wave_y - i * int(12 * scale) - int(8 * scale)
        wave_y2 = wave_y - i * int(12 * scale)
        draw.arc([wave_x1, wave_y1, wave_x2, wave_y2],
                 start=200, end=340, fill=wave_color, width=int(3 * scale))

    # ── 3. Mount arm (from dish center to pole) ──────────────
    arm_start_x = cx
    arm_start_y = cy - int(15 * scale)
    arm_end_x = cx
    arm_end_y = cy + int(50 * scale)
    arm_width = int(8 * scale)
    draw.rectangle(
        [arm_end_x - arm_width // 2, arm_start_y,
         arm_end_x + arm_width // 2, arm_end_y],
        fill=ARM_COLOR
    )

    # ── 4. Feed horn (on top of dish) ────────────────────────
    feed_x = cx
    feed_y = dish_y1 - int(25 * scale)
    feed_radius = int(12 * scale)
    draw.ellipse([feed_x - feed_radius, feed_y - feed_radius,
                  feed_x + feed_radius, feed_y + feed_radius],
                 fill=FEED_COLOR, outline=DISH_COLOR)

    # Feed inner dot
    inner_r = int(4 * scale)
    draw.ellipse([feed_x - inner_r, feed_y - inner_r,
                  feed_x + inner_r, feed_y + inner_r],
                 fill=DISH_HIGHLIGHT)

    # ── 5. Pole/base ─────────────────────────────────────────
    pole_width = int(10 * scale)
    pole_height = int(40 * scale)
    pole_x = cx - pole_width // 2
    pole_y = cy + int(45 * scale)
    draw.rectangle([pole_x, pole_y, pole_x + pole_width, pole_y + pole_height],
                   fill=POLE_COLOR)

    # Base plate
    base_width = int(40 * scale)
    base_height = int(6 * scale)
    base_x = cx - base_width // 2
    base_y = pole_y + pole_height
    draw.rectangle([base_x, base_y, base_x + base_width, base_y + base_height],
                   fill=POLE_COLOR)

    # ── 6. Small "C" letter for Chorus branding ──────────────
    try:
        font_size = int(28 * scale)
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # Draw "C" at bottom of dish
    text_bbox = draw.textbbox((0, 0), "C", font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_x = cx - text_w // 2
    text_y = cy + int(25 * scale)
    draw.text((text_x, text_y), "C", fill=DISH_HIGHLIGHT, font=font)

    # ── save as .ico with multiple sizes ─────────────────────
    # Create resized versions
    sizes = [16, 32, 48, 64, 128, 256]
    save_images = []
    for s in sizes:
        resized = img.resize((s, s), Image.LANCZOS)
        save_images.append(resized)

    save_images[0].save(
        output_path,
        format="ICO",
        sizes=[(im.size[0], im.size[1]) for im in save_images],
    )

    print(f"  Icon saved: {output_path}")
    print(f"  Sizes: {', '.join(str(s) for s in sizes)}")


def main() -> None:
    """Generate the Chorus satellite dish icon."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_path = os.path.join(project_root, "Chorus.ico")

    print()
    print("  Generating Chorus satellite dish icon...")
    print()
    generate_satellite_dish_icon(output_path)
    print()
    print("  Done!")
    print()


if __name__ == "__main__":
    main()
