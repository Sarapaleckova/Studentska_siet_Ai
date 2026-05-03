"""Thubnail generation for post files and previews."""

from pathlib import Path
import io
import base64

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def generate_thumbnail_from_file(file_path: Path, file_extension: str) -> str | None:
    """
    Generate a thumbnail image from an uploaded file.
    
    Returns a base64 data URI for the thumbnail, or None if generation fails.
    Supports images, PDF (via conversion), and generic file type icons.
    """
    if not PILLOW_AVAILABLE or not file_path.exists():
        return None
    
    ext = file_extension.lower()
    
    # Handle images
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
        return _generate_image_thumbnail(file_path)
    
    # Handle PDF
    if ext == '.pdf':
        return _generate_pdf_thumbnail(file_path)
    
    # For other types, return None (will use icon in template)
    return None


def _generate_image_thumbnail(file_path: Path) -> str | None:
    """Generate thumbnail from image file."""
    if not PILLOW_AVAILABLE:
        return None
    
    try:
        img = Image.open(file_path)
        
        # Convert RGBA to RGB for JPEG compatibility
        if img.mode in {'RGBA', 'LA', 'P'}:
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in {'RGBA', 'LA'} else None)
            img = rgb_img
        
        # Resize to thumbnail size (280x210 to match post card)
        img.thumbnail((280, 210), Image.Resampling.LANCZOS)
        
        # Create padding to exact size
        final_img = Image.new('RGB', (280, 210), (240, 240, 240))
        offset = ((280 - img.width) // 2, (210 - img.height) // 2)
        final_img.paste(img, offset)
        
        # Convert to base64 data URI
        buffer = io.BytesIO()
        final_img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"
    except Exception:
        return None


def _generate_pdf_thumbnail(file_path: Path) -> str | None:
    """Generate thumbnail from first page of PDF."""
    if not PILLOW_AVAILABLE:
        return None
    
    try:
        from pdf2image import convert_from_path
        
        pages = convert_from_path(file_path, first_page=1, last_page=1, dpi=100)
        if not pages:
            return None
        
        img = pages[0]
        img.thumbnail((280, 210), Image.Resampling.LANCZOS)
        
        # Create padding
        final_img = Image.new('RGB', (280, 210), (240, 240, 240))
        offset = ((280 - img.width) // 2, (210 - img.height) // 2)
        final_img.paste(img, offset)
        
        # Convert to base64
        buffer = io.BytesIO()
        final_img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"
    except Exception:
        return None


def get_file_icon_svg(file_extension: str) -> str:
    """
    Return an inline SVG icon for a file type.
    Returns as a data URI for use in templates.
    """
    ext = file_extension.lower()
    
    icons = {
        # Documents
        '.pdf': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#e74c3c" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">PDF</text><line x1="40" y1="80" x2="240" y2="80" stroke="#ccc" stroke-width="1"/><line x1="40" y1="95" x2="240" y2="95" stroke="#ccc" stroke-width="1"/><line x1="40" y1="110" x2="240" y2="110" stroke="#ccc" stroke-width="1"/><line x1="40" y1="125" x2="180" y2="125" stroke="#ccc" stroke-width="1"/></svg>',
        '.doc': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#4472c4" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">DOC</text><line x1="40" y1="80" x2="240" y2="80" stroke="#ccc" stroke-width="1"/><line x1="40" y1="95" x2="240" y2="95" stroke="#ccc" stroke-width="1"/><line x1="40" y1="110" x2="240" y2="110" stroke="#ccc" stroke-width="1"/><line x1="40" y1="125" x2="200" y2="125" stroke="#ccc" stroke-width="1"/></svg>',
        '.docx': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#4472c4" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">DOCX</text><line x1="40" y1="80" x2="240" y2="80" stroke="#ccc" stroke-width="1"/><line x1="40" y1="95" x2="240" y2="95" stroke="#ccc" stroke-width="1"/><line x1="40" y1="110" x2="240" y2="110" stroke="#ccc" stroke-width="1"/><line x1="40" y1="125" x2="200" y2="125" stroke="#ccc" stroke-width="1"/></svg>',
        
        # Spreadsheets
        '.xls': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#70ad47" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">XLS</text><g stroke="#ccc" stroke-width="1" fill="none"><line x1="40" y1="80" x2="240" y2="80"/><line x1="40" y1="95" x2="240" y2="95"/><line x1="40" y1="110" x2="240" y2="110"/><line x1="40" y1="125" x2="240" y2="125"/><line x1="100" y1="80" x2="100" y2="125"/><line x1="160" y1="80" x2="160" y2="125"/></g></svg>',
        '.xlsx': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#70ad47" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">XLSX</text><g stroke="#ccc" stroke-width="1" fill="none"><line x1="40" y1="80" x2="240" y2="80"/><line x1="40" y1="95" x2="240" y2="95"/><line x1="40" y1="110" x2="240" y2="110"/><line x1="40" y1="125" x2="240" y2="125"/><line x1="100" y1="80" x2="100" y2="125"/><line x1="160" y1="80" x2="160" y2="125"/></g></svg>',
        '.csv': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#70ad47" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="18" font-weight="bold" x="140" y="54" text-anchor="middle">CSV</text><g stroke="#ccc" stroke-width="1" fill="none"><line x1="40" y1="80" x2="240" y2="80"/><line x1="40" y1="95" x2="240" y2="95"/><line x1="40" y1="110" x2="240" y2="110"/><line x1="40" y1="125" x2="240" y2="125"/></g></svg>',
        
        # Presentations
        '.ppt': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#ed7d31" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">PPT</text><rect fill="#ffd89b" x="40" y="75" width="200" height="50"/><line x1="40" y1="130" x2="240" y2="130" stroke="#ccc" stroke-width="1"/><line x1="40" y1="145" x2="200" y2="145" stroke="#ccc" stroke-width="1"/></svg>',
        '.pptx': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#ed7d31" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="18" font-weight="bold" x="140" y="54" text-anchor="middle">PPTX</text><rect fill="#ffd89b" x="40" y="75" width="200" height="50"/><line x1="40" y1="130" x2="240" y2="130" stroke="#ccc" stroke-width="1"/><line x1="40" y1="145" x2="200" y2="145" stroke="#ccc" stroke-width="1"/></svg>',
        
        # Archives
        '.zip': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#9b7653" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">ZIP</text><line x1="50" y1="90" x2="230" y2="90" stroke="#ddd" stroke-width="3"/><circle cx="80" cy="120" r="8" fill="#ddd"/><circle cx="140" cy="120" r="8" fill="#ddd"/><circle cx="200" cy="120" r="8" fill="#ddd"/></svg>',
        '.rar': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#9b7653" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">RAR</text><line x1="50" y1="90" x2="230" y2="90" stroke="#ddd" stroke-width="3"/><circle cx="80" cy="120" r="8" fill="#ddd"/><circle cx="140" cy="120" r="8" fill="#ddd"/><circle cx="200" cy="120" r="8" fill="#ddd"/></svg>',
        
        # Text
        '.txt': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#666" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="20" font-weight="bold" x="140" y="54" text-anchor="middle">TXT</text><line x1="40" y1="80" x2="240" y2="80" stroke="#ccc" stroke-width="1"/><line x1="40" y1="95" x2="240" y2="95" stroke="#ccc" stroke-width="1"/><line x1="40" y1="110" x2="240" y2="110" stroke="#ccc" stroke-width="1"/><line x1="40" y1="125" x2="180" y2="125" stroke="#ccc" stroke-width="1"/></svg>',
        
        # Default
        'default': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 210"><rect fill="#f5f5f5" width="280" height="210"/><rect fill="#999" x="20" y="30" width="240" height="30" rx="4"/><text fill="white" font-size="18" font-weight="bold" x="140" y="54" text-anchor="middle">FILE</text><line x1="40" y1="80" x2="240" y2="80" stroke="#ccc" stroke-width="1"/><line x1="40" y1="95" x2="240" y2="95" stroke="#ccc" stroke-width="1"/><line x1="40" y1="110" x2="200" y2="110" stroke="#ccc" stroke-width="1"/></svg>',
    }
    
    svg_content = icons.get(ext, icons['default'])
    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_base64}"
