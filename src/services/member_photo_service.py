"""Authorized, bounded photo reads from the existing private photo directory."""
import io
import warnings
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from src.services.member_service import MEMBER_PHOTO_DIR, PROJECT_ROOT
from src.services.web_security import WebSecurityError

def member_photo(members, member_id):
    stored=members.get_photo_path(member_id)  # Authorize before probing the file.
    return safe_photo(stored)


def safe_photo(stored):
    """Encode only after the caller has authorized the stored member path."""
    try:
        if not stored: raise ValueError()
        root=MEMBER_PHOTO_DIR.resolve()
        candidate=Path(stored)
        path=(candidate if candidate.is_absolute() else PROJECT_ROOT/candidate).resolve(strict=True)
        if not path.is_relative_to(root) or path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:
            raise ValueError()
        if not path.is_file() or path.stat().st_size>8*1024*1024: raise ValueError()
        # Never emit original EXIF, file paths, SVG, or arbitrary file content.
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(path) as original:
                if original.width*original.height>16_000_000:raise ValueError()
                original.load()
                resized=ImageOps.exif_transpose(original)
                resized.thumbnail((512,512))
                output=io.BytesIO()
                resized.convert('RGB').save(output,format='JPEG',quality=85)
                return output.getvalue()
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise WebSecurityError(404,'RESOURCE_NOT_FOUND','The requested resource was not found.') from None
