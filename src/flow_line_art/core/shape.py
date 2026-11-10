"""The art's outer shape: its outline, how far a point lies inside it, and which modes can fill it."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property

NAMES = ("square", "circle", "rectangle", "oval", "hexagon")  # every shape the picker offers, in button order
TWO_SIZES = ("rectangle", "oval")  # the shapes with a separate width and height
SPIRAL_SHAPES = ("square", "circle", "rectangle")
SHAPES_BY_MODE = {
    "spiral": SPIRAL_SHAPES,
    "raster": NAMES,
    "hilbert": ("square",),
    "relief": SPIRAL_SHAPES,
    "calibration": ("circle",),
}
UNAVAILABLE_NOTES = {
    "spiral": "A spiral keeps even line spacing only in a circle, square or rectangle.",
    "relief": "Relief follows the spiral, which keeps even line spacing only in a circle, square or rectangle.",
    "hilbert": "A Hilbert curve only fills a square without breaking the line.",
    "calibration": "The calibration pattern is made for a disc.",
    "raster": "",
}
SEGMENTS = 180
EDGE_TEST_SEGMENTS = 45  # enough for an oval's inside test, and much faster than the full outline
HEXAGON_SIDES = 6
HEXAGON_HEIGHT_PER_WIDTH = math.sqrt(3) / 2  # corners point left and right, so width is across the corners


@dataclass(frozen=True)
class Shape:
    name: str
    width: float
    height: float

    @property
    def half_width(self) -> float:
        return self.width / 2

    @property
    def half_height(self) -> float:
        return self.height / 2

    def outline(self, segments: int = SEGMENTS) -> list:
        """Convex counter-clockwise outline around the origin."""
        hw, hh = self.half_width, self.half_height
        if self.name in ("square", "rectangle"):
            return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        if self.name == "hexagon":
            segments, hh = HEXAGON_SIDES, hw  # a regular hexagon: every corner lies on one circle
        return [(hw * math.cos(2 * math.pi * i / segments), hh * math.sin(2 * math.pi * i / segments)) for i in range(segments)]

    @cached_property
    def _planes(self) -> list:
        """Each edge as (normal x, normal y, offset); inside is where nx * x + ny * y <= offset."""
        polygon = self.outline(EDGE_TEST_SEGMENTS)
        planes = []
        for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
            length = math.hypot(bx - ax, by - ay)
            nx, ny = (by - ay) / length, (ax - bx) / length
            planes.append((nx, ny, nx * ax + ny * ay))
        return planes

    def inset(self, x: float, y: float) -> float:
        """How far a point lies inside the outline; negative outside."""
        if self.name == "circle":
            return self.half_width - math.hypot(x, y)
        if self.name in ("square", "rectangle"):
            return min(self.half_width - abs(x), self.half_height - abs(y))
        return min(offset - nx * x - ny * y for nx, ny, offset in self._planes)

    def row_span(self, y: float, inset: float) -> tuple | None:
        """Where a horizontal line at `y` runs at least `inset` inside the outline; None if nowhere."""
        left, right = -math.inf, math.inf
        for nx, ny, offset in self._planes:
            room = offset - inset - ny * y
            if abs(nx) < 1e-12:
                if room < 0:
                    return None
            elif nx > 0:
                right = min(right, room / nx)
            else:
                left = max(left, room / nx)
        return (left, right) if left < right else None


def make(name: str, width: float, height: float) -> Shape:
    """A shape with the sizes it uses: one number for a circle, square or hexagon."""
    if name in TWO_SIZES:
        return Shape(name, width, height)
    return Shape(name, width, width * HEXAGON_HEIGHT_PER_WIDTH if name == "hexagon" else width)


def page_table() -> dict:
    return {"shapes_by_mode": {mode: list(names) for mode, names in SHAPES_BY_MODE.items()}, "unavailable_notes": UNAVAILABLE_NOTES, "two_sizes": list(TWO_SIZES)}
