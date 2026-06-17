from PIL import Image
import sys

def create_icon(input_path, output_path):
    """Convert PNG to ICO with multiple sizes for Windows icon support."""
    try:
        img = Image.open(input_path)
        
        # Create multiple sizes for Windows icon
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icon_images = []
        
        for size in sizes:
            # Resize image to each size
            resized = img.resize(size, Image.Resampling.LANCZOS)
            icon_images.append(resized)
        
        # Save as ICO with all sizes
        icon_images[0].save(
            output_path,
            format='ICO',
            sizes=sizes,
            append_images=icon_images[1:]
        )
        
        print(f"✅ Icon created successfully: {output_path}")
        print(f"   Sizes included: {sizes}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating icon: {e}")
        return False

if __name__ == "__main__":
    input_file = r"d:\PROGRAMS\frogpaper-mainold\FrogPaperLogo.png"
    output_file = r"d:\PROGRAMS\frogpaper-mainold\frogpaper.ico"
    
    print(f"Converting {input_file} to {output_file}")
    create_icon(input_file, output_file)
