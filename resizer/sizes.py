"""Qwen Image 2.1 canvas selection, independent of ComfyUI and torch."""

import math
from functools import lru_cache


def validate_resolution(resolution):
    if type(resolution) is not int or not 0 <= resolution <= 4096 or resolution % 32:
        raise ValueError("resolution must be 0 or a multiple of 32 up to 4096")


def encoder_size(width, height, resolution):
    """Match TextEncodeQwenImage21's rounding, including resolution=0."""
    if resolution == 0:
        return max(32, round(width / 32) * 32), max(32, round(height / 32) * 32)
    ratio = width / height
    return (
        max(32, round(math.sqrt(resolution * resolution * ratio) / 32) * 32),
        max(32, round(math.sqrt(resolution * resolution / ratio) / 32) * 32),
    )


@lru_cache(maxsize=128)
def _fixed_sizes(resolution):
    n = resolution // 32
    area = n * n
    candidates = set()
    # A fixed pair (k,m) has |k*m-n*n| <= min(k,m)+1/4 <= n+1/4.
    # Its integer area therefore lies in [n*n-n, n*n+n]. At least
    # one side is <= n. Search that short side and verify exact rounding.
    for k in range(1, n + 1):
        low = max(k, (area - n + k - 1) // k)
        high = (area + n) // k
        for m in range(low, high + 1):
            for w, h in ((32 * k, 32 * m), (32 * m, 32 * k)):
                if encoder_size(w, h, resolution) == (w, h):
                    candidates.add((w, h))
    return tuple(sorted(candidates))


def select_size(width, height, resolution):
    if any(type(v) is not int or v <= 0 for v in (width, height)):
        raise ValueError("width and height must be positive integers")
    validate_resolution(resolution)
    if resolution == 0:
        return encoder_size(width, height, resolution)
    ratio = width / height
    # Preserve composition first; area error only breaks aspect-ratio ties.
    return min(
        _fixed_sizes(resolution),
        key=lambda size: (
            abs(math.log((size[0] / size[1]) / ratio)),
            abs(size[0] * size[1] - resolution * resolution),
            size,
        ),
    )
