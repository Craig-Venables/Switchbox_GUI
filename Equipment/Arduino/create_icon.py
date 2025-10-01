from PIL import Image, ImageDraw
import os

def create_tray_icon():
    """Create a simple thermometer icon for the system tray"""
    # Create a 64x64 image with transparent background
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw thermometer shape
    # Bulb (bottom circle)
    draw.ellipse([size//2-8, size-20, size//2+8, size-4], fill=(255, 100, 100), outline=(200, 50, 50), width=2)
    
    # Stem (vertical rectangle)
    draw.rectangle([size//2-3, 10, size//2+3, size-20], fill=(255, 100, 100), outline=(200, 50, 50), width=2)
    
    # Temperature scale lines
    for i in range(5):
        y = 15 + i * 8
        draw.line([size//2-6, y, size//2-1, y], fill=(200, 50, 50), width=1)
    
    # Save the icon
    icon_path = os.path.join(os.path.dirname(__file__), 'temp_icon.ico')
    img.save(icon_path, format='ICO', sizes=[(16, 16), (32, 32), (64, 64)])
    print(f"Icon created: {icon_path}")
    return icon_path

if __name__ == "__main__":
    create_tray_icon()
