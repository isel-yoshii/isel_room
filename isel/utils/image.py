from __future__ import annotations
import base64
import numpy as np
import cv2


def decode_image(data_url: str):
    img_bytes = base64.b64decode(data_url.split(',')[1])
    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
