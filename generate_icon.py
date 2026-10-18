"""Generate pathcut.ico — a simple geometric icon for PathCUT."""

from PIL import Image, ImageDraw, ImageFont
import math


def draw_icon(size: int) -> Image.Image:
    """Draw a single icon at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size  # shorthand
    pad = s * 0.06

    # --- Background: rounded rectangle, dark steel blue ---
    bg_color = (38, 50, 66)
    r = s * 0.18  # corner radius
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=r, fill=bg_color)

    # --- Steel plate shape (light grey rectangle, slightly tilted look) ---
    plate_color = (160, 175, 190)
    plate_l = s * 0.15
    plate_t = s * 0.22
    plate_r = s * 0.72
    plate_b = s * 0.78
    d.rectangle([plate_l, plate_t, plate_r, plate_b], fill=plate_color)

    # Inner cutout on the plate (darker hole)
    hole_color = (55, 68, 85)
    cx, cy = (plate_l + plate_r) / 2 - s * 0.04, (plate_t + plate_b) / 2
    hole_r = s * 0.08
    d.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=hole_color)

    # --- Cutting line: diagonal dashed line across the plate ---
    cut_color = (42, 180, 235)
    cut_width = max(2, int(s * 0.035))

    # Draw a bold diagonal cut line from top-right to bottom-left of plate
    x1, y1 = plate_r - s * 0.02, plate_t + s * 0.04
    x2, y2 = plate_l + s * 0.08, plate_b - s * 0.04

    # Draw dashed segments
    num_dashes = 5
    for i in range(num_dashes):
        t0 = i / num_dashes
        t1 = (i + 0.6) / num_dashes
        sx = x1 + (x2 - x1) * t0
        sy = y1 + (y2 - y1) * t0
        ex = x1 + (x2 - x1) * t1
        ey = y1 + (y2 - y1) * t1
        d.line([(sx, sy), (ex, ey)], fill=cut_color, width=cut_width)

    # --- Spark dots near the cut line (gives a cutting feel) ---
    spark_color = (255, 200, 60)
    # Place sparks near the middle of the cut line
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    spark_r = max(1, s * 0.018)
    offsets = [
        (s * 0.03, -s * 0.04),
        (-s * 0.04, -s * 0.02),
        (s * 0.05, s * 0.02),
        (-s * 0.02, s * 0.05),
    ]
    for ox, oy in offsets:
        sx, sy = mid_x + ox, mid_y + oy
        d.ellipse([sx - spark_r, sy - spark_r, sx + spark_r, sy + spark_r],
                  fill=spark_color)

    # --- "P" letter in bottom-right corner ---
    letter_color = (255, 255, 255)
    font_size = max(10, int(s * 0.32))
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    text = "P"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = s * 0.62
    ty = s * 0.52
    d.text((tx, ty), text, fill=letter_color, font=font)

    # --- Subtle border highlight ---
    border_color = (70, 90, 115)
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=r,
                        outline=border_color, width=max(1, int(s * 0.015)))

    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_icon(sz) for sz in sizes]

    # Save as .ico (multi-resolution)
    images[-1].save(
        "pathcut.ico",
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[:-1],
    )
    print(f"Created: pathcut.ico ({len(sizes)} sizes: {sizes})")

    # Also save a 256px PNG for preview
    images[-1].save("pathcut_icon_preview.png")
    print("Created: pathcut_icon_preview.png")


if __name__ == "__main__":
    main()
