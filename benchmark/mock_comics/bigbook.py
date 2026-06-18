#!/usr/bin/env python3
"""Create a big book for debugging page turning issues."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_SIZE = (200, 100)  # Width, Height
BG_COLOR = (255, 255, 255)  # White background
TEXT_COLOR = (0, 0, 0)  # Black text
FONT_SIZE = 60
FONT = ImageFont.truetype("SFNS.ttf", FONT_SIZE)


def create_number_images(output_dir: str, num_files: int):
    """Create number images."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(exist_ok=True)

    for i in range(num_files):
        img = Image.new("RGB", IMAGE_SIZE, color=BG_COLOR)
        d = ImageDraw.Draw(img)

        text = str(i)
        # Calculate text size using textbbox for more accurate centering
        bbox = d.textbbox((0, 0), text, font=FONT)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position to center the text
        x = (IMAGE_SIZE[0] - text_width) / 2
        y = (IMAGE_SIZE[1] - text_height) / 2

        d.text((x, y), text, fill=TEXT_COLOR, font=FONT)

        # Generate a unique filename (the naming convention can be customized)
        filename = f"number_{i:04d}.jpg"
        path = output_dir_path / filename

        # Save the image as a JPEG file
        img.save(path, "JPEG")
        print(f"Created: {path}")


def main():
    """Use cli args."""
    create_number_images(sys.argv[1], int(sys.argv[2]))


if __name__ == "__main__":
    main()
