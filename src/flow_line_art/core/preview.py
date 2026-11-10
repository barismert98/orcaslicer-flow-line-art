"""Rasterizes the real toolpath, so the preview shows what will be extruded."""
from __future__ import annotations

import math

from .art import Art

SHADE_PER_LAYER = 120  # how much one height step lightens or darkens a pixel
LIGHT_REACH = 3  # pixels between the two height samples of a slope


def _emboss(coverage: bytearray, height: bytearray, size: int) -> bytearray:
    """Adds raking light from the top left, the way a printed relief catches it."""
    shaded = bytearray(coverage)
    for y in range(LIGHT_REACH, size - LIGHT_REACH):
        for x in range(LIGHT_REACH, size - LIGHT_REACH):
            rise = height[(y + LIGHT_REACH) * size + x + LIGHT_REACH] - height[(y - LIGHT_REACH) * size + x - LIGHT_REACH]
            if rise:
                shaded[y * size + x] = min(255, max(0, coverage[y * size + x] - rise * SHADE_PER_LAYER))
    return shaded


def render(art: Art, size: int = 360) -> bytes:
    """Coverage 0..255 per pixel, row by row, top row first; 255 is solid line.

    A job with stacked passes also shows its height steps as light and shade.
    """
    outline = art.params.outline
    scale = size / max(outline.width, outline.height)
    half = size / 2
    buffer = bytearray(size * size)
    height = bytearray(size * size) if art.passes else None
    for index, ((ax, ay), (bx, by), width) in enumerate(zip(art.points, art.points[1:], art.widths)):
        raised = art.passes[index] - 1 if art.passes else 0
        radius = width / 2 * scale
        spacing = max(1.0, radius / 2)  # overlapping discs need not sit one pixel apart
        steps = max(1, math.ceil(math.hypot(bx - ax, by - ay) * scale / spacing))
        reach = math.ceil(radius + 1)
        for s in range(steps + 1):
            t = s / steps
            px = half + (ax + (bx - ax) * t) * scale
            py = half - (ay + (by - ay) * t) * scale
            x0, y0 = int(px), int(py)
            for iy in range(max(y0 - reach, 0), min(y0 + reach + 1, size)):
                row = iy * size
                dy = iy + 0.5 - py
                for ix in range(max(x0 - reach, 0), min(x0 + reach + 1, size)):
                    dx = ix + 0.5 - px
                    amount = radius + 0.5 - math.sqrt(dx * dx + dy * dy)
                    if amount <= 0:
                        continue
                    value = 255 if amount >= 1 else int(amount * 255)
                    if value > buffer[row + ix]:
                        buffer[row + ix] = value
                    if raised and amount >= 0.5 and raised > height[row + ix]:
                        height[row + ix] = raised
    return bytes(buffer if height is None else _emboss(buffer, height, size))
