"""Job parameters, machine values, and the path-with-widths they produce."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Callable

from . import toolpath
from .image import GrayImage, step_image, tone

MODES = ("spiral", "raster", "hilbert", "calibration")
COLOR_CHANGES = ("none", "pause")


class ArtError(ValueError):
    """A problem the user can fix by changing a setting."""


@dataclass(frozen=True)
class Machine:
    nozzle: float = 0.4
    filament_diameter: float = 1.75
    flow_ratio: float = 1.0
    max_volumetric: float = 15.0
    retract_length: float = 0.8
    retract_speed: float = 30.0
    deretract_speed: float = 30.0
    z_hop: float = 0.4
    travel_speed: float = 200.0
    relative_e: bool = True
    pause_gcode: str = ""
    bed: tuple[float, float, float, float] = (0.0, 0.0, 256.0, 256.0)  # min x, min y, max x, max y

    @property
    def filament_area(self) -> float:
        return math.pi * (self.filament_diameter / 2) ** 2


def _first(value, tool: int) -> str:
    parts = str(value).split(",")
    return parts[min(tool, len(parts) - 1)].strip()


def machine_from_config(get: Callable[[str], object], tool: int = 0) -> Machine:
    """Read a Machine from a resolved config getter; missing keys keep their defaults."""
    base = Machine()

    def number(key: str, default: float) -> float:
        raw = get(key)
        if raw in (None, ""):
            return default
        try:
            return float(_first(raw, tool))
        except ValueError:
            return default

    bed = base.bed
    area = get("printable_area")
    if area:
        xs, ys = zip(*(tuple(float(c) for c in p.split("x")) for p in str(area).split(",")))
        bed = (min(xs), min(ys), max(xs), max(ys))
    relative = get("use_relative_e_distances")
    pause = get("machine_pause_gcode")
    return Machine(
        nozzle=number("nozzle_diameter", base.nozzle),
        filament_diameter=number("filament_diameter", base.filament_diameter),
        flow_ratio=number("filament_flow_ratio", base.flow_ratio),
        max_volumetric=number("filament_max_volumetric_speed", base.max_volumetric),
        retract_length=number("retraction_length", base.retract_length),
        retract_speed=number("retraction_speed", base.retract_speed),
        deretract_speed=number("deretraction_speed", base.deretract_speed) or number("retraction_speed", base.retract_speed),
        z_hop=number("z_hop", base.z_hop),
        travel_speed=number("travel_speed", base.travel_speed),
        relative_e=str(relative) not in ("0", "false") if relative is not None else True,
        pause_gcode=str(pause).replace("\\n", "\n") if pause else "",
        bed=bed,
    )


@dataclass(frozen=True)
class Params:
    mode: str = "spiral"
    diameter: float = 60.0
    pitch: float = 0.65
    chord: float = 0.5
    width_min: float = 0.24
    width_max: float = 0.64
    invert: bool = False
    gamma: float = 1.0
    contrast: float = 1.0
    ring: float = 2.0
    speed: float = 40.0
    slew: float = 0.15  # mm of line width per mm of path
    margin: float = 0.4
    base_layers: int = 4
    color_change: str = "pause"
    steps: int = 8
    flow: float = 1.0  # multiplies the extrusion of the art line
    art_layers: int = 1
    nozzle: float = 0.0  # 0: the printer preset's nozzle
    layer_height: float = 0.0  # 0: whatever the slice uses
    base_filament: int = 1  # 1-based slot in the project
    art_filament: int = 1

    @property
    def square(self) -> bool:
        """A square base of side `diameter`, instead of a disc."""
        return self.mode == "hilbert"

    @property
    def two_filaments(self) -> bool:
        return self.base_filament != self.art_filament

    @property
    def half_span(self) -> float:
        """How far the line's centre reaches from the middle of the base."""
        return self.diameter / 2 - self.margin - self.width_max / 2

    @classmethod
    def from_dict(cls, data: dict) -> "Params":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        fields = cls.__dataclass_fields__
        converted = {}
        for key, value in known.items():
            kind = {"str": str, "bool": bool, "int": int, "float": float}[fields[key].type]
            converted[key] = kind(value)
        return cls(**converted)

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self, machine: Machine) -> None:
        if self.mode not in MODES:
            raise ArtError(f"Unknown mode: {self.mode}")
        if self.color_change not in COLOR_CHANGES:
            raise ArtError(f"Unknown colour change: {self.color_change}")
        if self.diameter < 10:
            raise ArtError("Diameter must be at least 10 mm.")
        if self.pitch <= 0 or self.chord <= 0:
            raise ArtError("Pitch and chord length must be positive.")
        if self.width_min >= self.width_max:
            raise ArtError("Minimum width must be below maximum width.")
        if self.width_min < 0.5 * machine.nozzle:
            raise ArtError(f"Minimum width must be at least {0.5 * machine.nozzle:.2f} mm for this nozzle.")
        if self.width_max > 2.0 * machine.nozzle:
            raise ArtError(f"Maximum width must be at most {2.0 * machine.nozzle:.2f} mm for this nozzle.")
        if self.width_max > self.pitch * 1.1:
            raise ArtError("Maximum width must not exceed the line pitch by more than 10 %.")
        if self.gamma <= 0 or self.contrast <= 0:
            raise ArtError("Gamma and contrast must be positive.")
        if self.speed <= 0 or self.slew <= 0:
            raise ArtError("Speed and width change limit must be positive.")
        if self.ring < 0:
            raise ArtError("Ring width cannot be negative.")
        if self.base_layers < 1:
            raise ArtError("The base disc needs at least one layer.")
        if self.steps < 2:
            raise ArtError("Calibration needs at least two steps.")
        if not 0.5 <= self.flow <= 1.5:
            raise ArtError("Flow multiplier must be between 0.5 and 1.5.")
        if self.base_filament < 1 or self.art_filament < 1:
            raise ArtError("Filament numbers start at 1.")
        if not 1 <= self.art_layers <= 10:
            raise ArtError("Art layers must be between 1 and 10.")
        if self.nozzle and not 0.1 <= self.nozzle <= 1.2:
            raise ArtError("Nozzle diameter must be between 0.1 and 1.2 mm.")
        if self.layer_height and not 0.04 <= self.layer_height <= 0.8 * machine.nozzle:
            raise ArtError(f"Layer height must be between 0.04 and {0.8 * machine.nozzle:.2f} mm for this nozzle.")


@dataclass(frozen=True)
class Art:
    points: list  # centred on the origin
    widths: list  # one per segment, len(points) - 1
    layer_height: float
    speed: float  # mm/s, constant along the line
    params: Params
    machine: Machine

    def lengths(self) -> list:
        return [math.dist(a, b) for a, b in zip(self.points, self.points[1:])]

    def stats(self) -> dict:
        lengths = self.lengths()
        layers = self.params.art_layers
        total = sum(lengths) * layers
        volume = sum(w * self.layer_height * l for w, l in zip(self.widths, lengths)) * layers * self.params.flow
        return {
            "segments": len(self.widths),
            "length_mm": total,
            "volume_mm3": volume,
            "filament_mm": volume / self.machine.filament_area,
            "time_s": total / self.speed,
            "width_min": min(self.widths),
            "width_max": max(self.widths),
            "speed": self.speed,
            "max_flow": max(self.widths) * self.layer_height * self.speed * self.params.flow,
        }


def target_width(brightness: float, params: Params) -> float:
    """Darker image parts give a wider line, unless inverted."""
    level = tone(brightness, params.contrast, params.gamma)
    amount = level if params.invert else 1.0 - level
    return params.width_min + (params.width_max - params.width_min) * amount


def slew_limited(widths: list, lengths: list, slew: float) -> list:
    """Zero-phase limit on width change: the mean of forward and backward passes."""
    forward = list(widths)
    for i in range(1, len(forward)):
        step = slew * lengths[i]
        forward[i] = min(max(forward[i], forward[i - 1] - step), forward[i - 1] + step)
    backward = list(widths)
    for i in range(len(backward) - 2, -1, -1):
        step = slew * lengths[i + 1]
        backward[i] = min(max(backward[i], backward[i + 1] - step), backward[i + 1] + step)
    return [(a + b) / 2 for a, b in zip(forward, backward)]


def limited_speed(params: Params, machine: Machine, layer_height: float) -> float:
    """Constant speed that keeps flow within the volumetric limit at the widest line."""
    return min(params.speed, machine.max_volumetric / (params.width_max * layer_height * params.flow))


def build(params: Params, image: GrayImage | None, machine: Machine, layer_height: float) -> Art:
    if params.nozzle:
        machine = replace(machine, nozzle=params.nozzle)
    params.validate(machine)
    if layer_height <= 0:
        raise ArtError("Layer height must be positive.")
    radius = params.half_span
    if radius <= params.pitch:
        raise ArtError("The disc is too small for this pitch and width.")
    if params.ring >= radius:
        raise ArtError("The ring is wider than the disc.")
    if params.mode == "calibration":
        params_for_tone = Params(**{**params.to_dict(), "gamma": 1.0, "contrast": 1.0, "invert": False, "ring": 0.0})
        image = step_image(params.steps)
        points = toolpath.raster(radius, params.pitch, params.chord)
    else:
        params_for_tone = params
        if image is None:
            raise ArtError("Pick an image first.")
        image = image.center_square()
        path = {"spiral": toolpath.spiral, "raster": toolpath.raster, "hilbert": toolpath.hilbert}[params.mode]
        points = path(radius, params.pitch, params.chord)

    widths = []
    lengths = []
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        mx, my = (ax + bx) / 2, (ay + by) / 2
        lengths.append(math.hypot(bx - ax, by - ay))
        brightness = image.sample((mx / radius + 1) / 2, (1 - my / radius) / 2)
        wanted = target_width(brightness, params_for_tone)
        reach = max(abs(mx), abs(my)) if params.square else math.hypot(mx, my)
        if params_for_tone.ring and reach >= radius - params_for_tone.ring:
            wanted = params_for_tone.width_max
        widths.append(min(max(wanted, params.width_min), params.width_max))
    widths = slew_limited(widths, lengths, params.slew)
    return Art(points, widths, layer_height, limited_speed(params, machine, layer_height), params, machine)


def hilbert_info(params: Params) -> dict:
    """The line spacing a Hilbert curve gets at this size, and the sizes that give the asked pitch."""
    order = toolpath.hilbert_order(params.half_span, params.pitch)
    pitch = 2 * params.half_span / (2**order - 1) if order else 0.0
    edge = 2 * params.margin + params.width_max
    sizes = [math.ceil(((2**n - 1) * params.pitch + edge) * 10 - 1e-6) / 10 for n in range(2, 10)]
    return {"pitch": pitch, "sizes": [size for size in sizes if 15 <= size <= 300]}


def gamma_from_step(index: int, steps: int) -> float:
    """Gamma that maps mid-gray to the printed step that looks mid-gray (0-based, black first)."""
    if not 0 < index < steps - 1:
        raise ArtError("Pick a step between the darkest and the lightest.")
    darkness = 1.0 - index / (steps - 1)
    return math.log(1.0 - darkness) / math.log(0.5)
