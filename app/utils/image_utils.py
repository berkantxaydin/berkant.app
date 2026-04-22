import base64
import io
from PIL import Image
from typing import Optional, Tuple

def save_image_as_base64(file_obj, max_size: Tuple[int, int] = (400, 400)) -> Optional[str]:
    """
    Processes an uploaded image file:
    - Opens with Pillow
    - Converts to RGB/RGBA as needed
    - Resizes to fit within max_size
    - Saves as PNG
    - Returns a Base64 data URI string
    """
    if not file_obj:
        return None
    
    try:
        # 1. Open the image
        img = Image.open(file_obj)
        
        # 2. Resize maintaining aspect ratio if it exceeds max_size
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # 3. Convert to RGBA if necessary to preserve transparency in PNG
        if img.mode in ("P", "L"):
            img = img.convert("RGBA")
        elif img.mode == "RGB":
            # Keep as RGB or convert to RGBA, PNG handles both. 
            # RGBA is safer for general use.
            img = img.convert("RGBA")
            
        # 4. Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        
        # 5. Encode as Base64
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_str}"
        
    except Exception as e:
        print(f"Image processing error: {e}")
        return None
