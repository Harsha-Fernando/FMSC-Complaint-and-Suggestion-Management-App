"""Upload checks for evidence files (Sections 5.1, 12 and 15).

Each file is checked three ways: its extension, its size, and its first bytes.
The last check stops someone renaming a script to "photo.jpg".
"""

from django.utils.translation import gettext_lazy as gettext
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

from .models import Attachment

IMAGE_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
VIDEO_CONTENT_TYPES = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
}


def _read_head(uploaded, length=32):
    uploaded.seek(0)
    head = uploaded.read(length)
    uploaded.seek(0)
    return head


def _image_signature_ok(ext, head):
    if ext in {"jpg", "jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def _video_signature_ok(ext, head):
    if ext in {"mp4", "mov"}:
        return head[4:8] in {b"ftyp", b"moov", b"wide", b"mdat", b"free", b"skip"}
    if ext == "webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    return False


def validate_upload(uploaded, expected_type):
    """Return (file_type, content_type) or raise ValidationError with a clear message."""
    name = uploaded.name
    ext = Path(name).suffix.lower().lstrip(".")

    if expected_type == Attachment.FileType.IMAGE:
        allowed = settings.ALLOWED_IMAGE_EXTENSIONS
        limit_mb = settings.MAX_IMAGE_SIZE_MB
        content_types = IMAGE_CONTENT_TYPES
        signature_ok = _image_signature_ok
        label = "image"
    else:
        allowed = settings.ALLOWED_VIDEO_EXTENSIONS
        limit_mb = settings.MAX_VIDEO_SIZE_MB
        content_types = VIDEO_CONTENT_TYPES
        signature_ok = _video_signature_ok
        label = "video"

    if ext not in allowed:
        raise ValidationError(
            gettext("“%(value_0)s” is not an accepted %(value_1)s type. Use %(value_2)s.") % {'value_0': name, 'value_1': label, 'value_2': ', '.join(allowed).upper()}
        )
    if uploaded.size > limit_mb * 1024 * 1024:
        raise ValidationError(
            gettext("“%(value_0)s” is %(value_1)s. %(value_2)ss must be %(value_3)s MB or smaller.") % {'value_0': name, 'value_1': filesizeformat(uploaded.size), 'value_2': label.capitalize(), 'value_3': limit_mb}
        )
    if uploaded.size == 0:
        raise ValidationError(gettext("“%(value_0)s” is empty. Choose the file again.") % {'value_0': name})
    if not signature_ok(ext, _read_head(uploaded)):
        raise ValidationError(
            gettext("“%(value_0)s” does not look like a real %(value_1)s file. Export it again from your phone or camera and retry.") % {'value_0': name, 'value_1': ext.upper()}
        )

    if expected_type == Attachment.FileType.IMAGE:
        # Pillow catches truncated or corrupted images that pass the header check.
        try:
            from PIL import Image

            uploaded.seek(0)
            with Image.open(uploaded) as img:
                img.verify()
        except Exception as exc:
            raise ValidationError(gettext("“%(value_0)s” could not be opened as an image.") % {'value_0': name}) from exc
        finally:
            uploaded.seek(0)

    return expected_type, content_types[ext]
