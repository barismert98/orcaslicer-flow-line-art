"""Toolpaths about the origin, in millimetres. Each is one unbroken polyline."""
from __future__ import annotations

import math

Point = tuple[float, float]


def spiral(radius: float, pitch: float, chord: float) -> list[Point]:
    """Archimedean spiral from the centre outward, with near-constant chord length."""
    if radius <= pitch:
        raise ValueError("the spiral needs a radius larger than its pitch")
    a = pitch / (2 * math.pi)
    theta = 2 * math.pi  # starts one pitch from the centre, where the curve is printable
    points = [(a * theta * math.cos(theta), a * theta * math.sin(theta))]
    while True:
        r = a * theta
        step = chord / math.hypot(r, a)
        for _ in range(3):  # correct the first-order step to the true chord
            nr = a * (theta + step)
            length = math.sqrt(r * r + nr * nr - 2 * r * nr * math.cos(step))
            step *= chord / length
        theta += step
        r = a * theta
        if r > radius:
            return points
        points.append((r * math.cos(theta), r * math.sin(theta)))


def _subdivide(start: Point, end: Point, chord: float) -> list[Point]:
    """Points after `start` up to and including `end`, at most `chord` apart."""
    length = math.dist(start, end)
    count = max(1, math.ceil(length / chord - 1e-9))
    return [
        (start[0] + (end[0] - start[0]) * i / count, start[1] + (end[1] - start[1]) * i / count)
        for i in range(1, count + 1)
    ]


def hilbert_order(half: float, pitch: float) -> int:
    """Finest curve whose line spacing inside +/-half is not below `pitch`; 0 if none fits."""
    order = 0
    while 2 * half / (2 ** (order + 1) - 1) >= pitch * (1 - 1e-9):
        order += 1
    return order


def _hilbert_cell(order: int, index: int) -> tuple[int, int]:
    x = y = 0
    rest = index
    for level in range(order):
        size = 1 << level
        rx = 1 & (rest // 2)
        ry = 1 & (rest ^ rx)
        if ry == 0:
            if rx == 1:
                x, y = size - 1 - x, size - 1 - y
            x, y = y, x
        x += size * rx
        y += size * ry
        rest //= 4
    return x, y


def hilbert(half: float, pitch: float, chord: float) -> list[Point]:
    """Hilbert curve filling the square +/-half, its spacing snapped to fit that square."""
    order = hilbert_order(half, pitch)
    if order < 2:
        raise ValueError("The square is too small for a Hilbert curve at this pitch.")
    cells = 1 << order
    step = 2 * half / (cells - 1)
    corners = [_hilbert_cell(order, index) for index in range(cells * cells)]
    points = [(-half + corners[0][0] * step, -half + corners[0][1] * step)]
    for x, y in corners[1:]:
        points.extend(_subdivide(points[-1], (-half + x * step, -half + y * step), chord))
    return points


def raster(radius: float, pitch: float, chord: float) -> list[Point]:
    """Serpentine lines clipped to a circle, joined at their ends into one polyline."""
    if radius <= pitch:
        raise ValueError("the raster needs a radius larger than its pitch")
    rows = int(2 * radius / pitch)
    first = (rows * pitch) / 2
    points: list[Point] = []
    for index in range(rows + 1):
        y = first - index * pitch
        half = math.sqrt(max(radius * radius - y * y, 0.0))
        if half < chord:
            continue
        ends = ((-half, y), (half, y)) if len(points) == 0 or index % 2 == 0 else ((half, y), (-half, y))
        if points:
            points.extend(_subdivide(points[-1], ends[0], chord))
        else:
            points.append(ends[0])
        points.extend(_subdivide(ends[0], ends[1], chord))
    return points
