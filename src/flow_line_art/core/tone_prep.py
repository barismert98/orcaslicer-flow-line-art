"""Prepares a picture so the line's width range is spent on what the picture really contains."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from itertools import accumulate
from operator import sub

from .image import GrayImage

CLIP_FRACTION = 0.01  # a few specular or black pixels must not set the range
MIN_SPAN = 16  # below this a picture is blank, and stretching would only magnify noise
MIDTONE_TARGET = 0.6  # where the median lands; light of the middle, because the line can never be thinner than its minimum
EXTREME_MEDIAN = 0.05  # keeps the midtone exponent finite for pictures that are almost all one tone
SHARPEN_AMOUNT = 0.8
SHARPEN_RADIUS_FRACTION = 1 / 105  # of the picture's side: about one line spacing on a typical disc
MAX_LEVEL = 255


def _percentile(counts: Counter, total: int, fraction: float) -> int:
    target = fraction * total
    seen = 0
    for level in sorted(counts):
        seen += counts[level]
        if seen >= target:
            return level
    return MAX_LEVEL


def _tone_table(low: int, high: int, median: int, midtone: float) -> bytes:
    span = high - low
    position = min(max((median - low) / span, EXTREME_MEDIAN), 1.0 - EXTREME_MEDIAN)
    exponent = math.log(midtone) / math.log(position)
    return bytes(round(MAX_LEVEL * min(max((level - low) / span, 0.0), 1.0) ** exponent) for level in range(MAX_LEVEL + 1))


def _box_line(line: bytes, radius: int) -> bytes:
    """Running mean of one row or column; prefix sums keep it fast in pure Python."""
    window = 2 * radius + 1
    padded = bytes(line[:1]) * (radius + 1) + line + bytes(line[-1:]) * radius
    running = list(accumulate(padded))
    return bytes(map(window.__rfloordiv__, map(sub, running[window:], running)))


def _blurred(image: GrayImage, radius: int) -> bytes:
    width, height = image.width, image.height
    rows = b"".join(_box_line(image.data[y * width : (y + 1) * width], radius) for y in range(height))
    columns = bytearray(len(rows))
    for x in range(width):
        columns[x::width] = _box_line(rows[x::width], radius)
    return bytes(columns)


def sharpen(image: GrayImage) -> GrayImage:
    """Unsharp mask: raises local contrast at edges and leaves even areas as they are."""
    radius = max(1, round(min(image.width, image.height) * SHARPEN_RADIUS_FRACTION))
    soft = _blurred(image, radius)
    data = bytes(min(MAX_LEVEL, max(0, round(level + SHARPEN_AMOUNT * (level - mean)))) for level, mean in zip(image.data, soft))
    return replace(image, data=data)


def prepare(image: GrayImage, inverted: bool = False) -> GrayImage:
    """Stretches the picture over its real range without its outliers, then sharpens it.

    `inverted` mirrors the midtone target, because an inverted job prints the light parts.
    """
    counts = Counter(image.data)
    total = len(image.data)
    low, high = _percentile(counts, total, CLIP_FRACTION), _percentile(counts, total, 1.0 - CLIP_FRACTION)
    if high - low < MIN_SPAN:
        return image
    midtone = 1.0 - MIDTONE_TARGET if inverted else MIDTONE_TARGET
    table = _tone_table(low, high, _percentile(counts, total, 0.5), midtone)
    return sharpen(replace(image, data=image.data.translate(table)))
