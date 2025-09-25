#!/usr/bin/env python3
"""
Pillow Font Test with Roboto Regular
Test font rendering capabilities for GUI text display
"""

from PIL import Image, ImageDraw, ImageFont
import os

def test_font_rendering():
    """Test font rendering with Roboto Regular"""

    # Create a test image
    width, height = 800, 600
    background_color = (255, 255, 255)  # White
    text_color = (0, 0, 0)  # Black

    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Use the extracted Roboto Regular font
    font_path = 'fonts/static/Roboto-Regular.ttf'

    if os.path.exists(font_path):
        print(f"Using font: {font_path}")

        # Test different font sizes
        font_sizes = [12, 16, 20, 24, 32, 48]
        current_y = 50

        for size in font_sizes:
            try:
                font = ImageFont.truetype(font_path, size)
                test_text = f"Roboto Regular {size}px - MultiModal Tracker GUI"

                # Draw text
                draw.text((50, current_y), test_text, font=font, fill=text_color)
                current_y += size + 10

            except Exception as e:
                print(f"Error with font size {size}: {e}")
                continue
    else:
        print(f"Font not found: {font_path}")
        return None

    # Save test image
    output_path = 'font_test_output.png'
    image.save(output_path)
    print(f"Font test image saved to: {output_path}")

    return output_path

def test_gui_text_samples():
    """Test specific GUI text that will be used in the application"""

    width, height = 400, 300
    image = Image.new('RGB', (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(image)

    font_path = 'fonts/static/Roboto-Regular.ttf'

    try:
        font_small = ImageFont.truetype(font_path, 14)
        font_medium = ImageFont.truetype(font_path, 16)
        font_large = ImageFont.truetype(font_path, 20)
        print("Successfully loaded Roboto fonts")
    except Exception as e:
        print(f"Error loading fonts: {e}")
        font_small = font_medium = font_large = ImageFont.load_default()

    # GUI text samples
    gui_elements = [
        ("MultiModal Tracker", font_large, (50, 20), (0, 0, 0)),
        ("Status: Running", font_medium, (50, 50), (0, 128, 0)),
        ("Hand Detection: ON", font_small, (50, 80), (0, 0, 255)),
        ("Face Detection: OFF", font_small, (50, 100), (128, 128, 128)),
        ("Pose Detection: ON", font_small, (50, 120), (0, 0, 255)),
        ("FPS: 29.8", font_small, (50, 150), (0, 0, 0)),
        ("OSC: 127.0.0.1:8000", font_small, (50, 170), (0, 0, 0)),
        ("Press 'Q' to quit", font_small, (50, 200), (128, 0, 0)),
    ]

    for text, font, position, color in gui_elements:
        draw.text(position, text, font=font, fill=color)

    output_path = 'gui_text_test.png'
    image.save(output_path)
    print(f"GUI text test saved to: {output_path}")

    return output_path

if __name__ == "__main__":
    print("Testing Pillow font rendering with Roboto Regular...")
    print("=" * 50)

    # Check font availability
    font_path = 'fonts/static/Roboto-Regular.ttf'
    print(f"Font path: {font_path}")
    print(f"Font exists: {os.path.exists(font_path)}")

    if os.path.exists(font_path):
        # Run font tests
        test_font_rendering()
        test_gui_text_samples()

        print("=" * 50)
        print("Font tests completed successfully!")
        print("Check font_test_output.png and gui_text_test.png")
    else:
        print("Error: Roboto-Regular.ttf not found!")
        print("Please ensure the font file is in fonts/static/ directory")