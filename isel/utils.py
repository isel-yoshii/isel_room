from __future__ import annotations
import base64
from datetime import datetime
from functools import wraps
import numpy as np
import cv2
from flask import session, jsonify


def month_range(year: int, month: int) -> tuple[datetime, datetime]:
    """The half-open range [start, end) covering one calendar month.

    `end` is the first instant of the *next* month, so queries must use `<`, not
    `<=`. Half-open on purpose: the inclusive `23:59:59` bound this replaces
    silently dropped anything in the final second of the month.
    """
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    return start, end


def minutes_between(start: datetime, end: datetime) -> int:
    """Whole minutes from start to end, truncated."""
    return int((end - start).total_seconds() / 60)


def ok(message: str | None = None, **extra):
    """Standard success JSON: 200 + {success: True, message?, ...extra}."""
    payload = {'success': True}
    if message is not None:
        payload['message'] = message
    payload.update(extra)
    return jsonify(payload)


def fail(message: str, status: int = 400, **extra):
    """Standard error JSON: (status, {success: False, message, ...extra})."""
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


_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB — plenty for a webcam JPEG


class ImageDecodeError(ValueError):
    pass


class ApiError(Exception):
    """Something the caller can fix — a missing record, an invalid field.

    Services raise this instead of returning {'success': False, ...}; the app's
    error handler turns it into the same JSON body every route used to build by
    hand. Anything *not* raised as an ApiError is a bug, gets logged with a
    traceback, and is reported to the caller as a generic 500.
    """

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def decode_image(data_url: str):
    """Decode a data: URL into an OpenCV BGR frame.

    Returns None if the data is malformed or not a valid image — callers
    treat that the same as "no face detected". Raises ImageDecodeError
    only for oversized payloads, so we never allocate huge buffers.
    """
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
