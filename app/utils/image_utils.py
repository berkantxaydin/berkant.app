import base64
import io
from PIL import Image, ImageOps
from typing import Optional, Tuple

def optimize_base64_image(base64_str: str, max_size: Tuple[int, int] = (1024, 1024)) -> Optional[str]:
    """
    Takes a base64 data URI, optimizes it (resizes while preserving aspect ratio, 
    converts to WebP), and returns a new optimized base64 data URI.
    """
    if not base64_str or not base64_str.startswith("data:image/"):
        return base64_str

    try:
        # Extract the actual base64 data
        header, data = base64_str.split(',', 1)
        image_data = base64.b64decode(data)
        
        return _process_image_to_webp(io.BytesIO(image_data), max_size)
        
    except Exception as e:
        print(f"Base64 optimization error: {e}")
        return base64_str

def save_image_as_base64(file_obj, max_size: Tuple[int, int] = (1024, 1024)) -> Optional[str]:
    """
    Processes an uploaded image file into an optimized WebP Base64 string.
    Ensures aspect ratio is preserved (no squashing into squares).
    """
    if not file_obj:
        return None
    
    try:
        return _process_image_to_webp(file_obj, max_size)
    except Exception as e:
        print(f"Image processing error: {e}")
        return None

def _process_image_to_webp(file_source, max_size: Tuple[int, int]) -> Optional[str]:
    """Internal helper to process image with best practices."""
    img = Image.open(file_source)
    
    # Handle EXIF orientation (fixes rotated mobile uploads)
    img = ImageOps.exif_transpose(img)
    
    # Preserve transparency if present
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # thumbnail() natively maintains aspect ratio and only downsizes
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    buffer = io.BytesIO()
    # Higher quality (90) for premium visuals, method 6 for best possible compression at that quality
    img.save(buffer, format="WEBP", quality=90, method=6)
    
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/webp;base64,{img_str}"
