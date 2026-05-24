from __future__ import annotations
import base64
from functools import wraps
import numpy as np
import cv2
from flask import session, jsonify


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB — plenty for a webcam JPEG


class ImageDecodeError(ValueError):
    pass


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
