"""Color-matching post-processing for AI hair swap results.

After SD 1.5 inpainting the result often has a different white-balance and
skin-tone than the original selfie.  This module performs histogram matching
in Lab colour space using the *whole* original image as the reference and
blends the result 60/40 to keep the original lighting feel.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def match_colors(original_bytes: bytes, result_bytes: bytes) -> bytes:
    """Match the colour histogram of *result* to *original* in Lab space.

    Returns JPEG bytes of the colour-matched result.
    """
    orig = cv2.imdecode(np.frombuffer(original_bytes, np.uint8), cv2.IMREAD_COLOR)
    result = cv2.imdecode(np.frombuffer(result_bytes, np.uint8), cv2.IMREAD_COLOR)

    if orig is None or result is None:
        logger.warning("Color match: could not decode images, returning result as-is")
        return result_bytes

    if orig.shape != result.shape:
        result = cv2.resize(result, (orig.shape[1], orig.shape[0]))

    orig_lab = cv2.cvtColor(orig, cv2.COLOR_BGR2Lab)
    result_lab = cv2.cvtColor(result, cv2.COLOR_BGR2Lab)

    matched = np.zeros_like(result_lab)
    for c in range(3):
        src = orig_lab[:, :, c]
        ref = result_lab[:, :, c]
        src_hist = np.bincount(src.ravel(), minlength=256)
        ref_hist = np.bincount(ref.ravel(), minlength=256)
        src_cdf = np.cumsum(src_hist).astype(np.float64) / max(src.size, 1)
        ref_cdf = np.cumsum(ref_hist).astype(np.float64) / max(ref.size, 1)

        lut = np.zeros(256, dtype=np.uint8)
        j = 0
        for i in range(256):
            while j < 256 and ref_cdf[j] < src_cdf[i]:
                j += 1
            lut[i] = min(j, 255)
        matched[:, :, c] = lut[ref.ravel()].reshape(ref.shape)

    matched_bgr = cv2.cvtColor(matched, cv2.COLOR_Lab2BGR)

    blended = cv2.addWeighted(matched_bgr, 0.6, result, 0.4, 0)

    _, encoded = cv2.imencode(".jpg", blended, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()
