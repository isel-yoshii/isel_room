from __future__ import annotations
import base64
from datetime import datetime
from functools import wraps
import numpy as np
import cv2
from flask import session, jsonify


def month_range(year: int, month: int) -> tuple[datetime, datetime]:
    """Half-open [start, end) for one calendar month — query with `<`, not `<=`.

    The inclusive `23:59:59` bound this replaces dropped the final second.
    """
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    return start, end


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() / 60)


def ok(message: str | None = None, **extra):
    payload = {'success': True}
    if message is not None:
        payload['message'] = message
    payload.update(extra)
    return jsonify(payload)


def fail(message: str, status: int = 400, **extra):
    payload = {'success': False, 'message': message}
    payload.update(extra)
    return jsonify(payload), status


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return fail('Admin access required', 403)
        return f(*args, **kwargs)
    return decorated


_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ImageDecodeError(ValueError):
    pass


class ApiError(Exception):
    """Something the caller can fix. Anything *not* raised as an ApiError is a
    bug: it gets logged with a traceback and reported as a generic 500."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def decode_image(data_url: str):
    """Decode a data: URL into an OpenCV BGR frame. None = malformed, which
    callers treat as "no face detected"; oversized raises before allocating."""
    if not isinstance(data_url, str) or ',' not in data_url:
        return None

    b64_part = data_url.split(',', 1)[1]
    if len(b64_part) * 3 // 4 > _MAX_IMAGE_BYTES:
        raise ImageDecodeError('Image exceeds 5 MB limit')

    try:
        img_bytes = base64.b64decode(b64_part)
    except (ValueError, TypeError):
        return None

    if len(img_bytes) > _MAX_IMAGE_BYTES:
        raise ImageDecodeError('Image exceeds 5 MB limit')

    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
