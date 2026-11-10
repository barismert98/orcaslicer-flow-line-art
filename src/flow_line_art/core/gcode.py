"""Turns an Art into G-code lines placed on the bed at a given center."""
from __future__ import annotations

from .art import Art

START_MARK = "; FLOW_LINE_ART_START"
END_MARK = "; FLOW_LINE_ART_END"
Z_FEED = 1200  # mm/min, gentle on the plunge back to the print surface


def _num(value: float, digits: int) -> str:
    text = f"{value:.{digits}f}"
    if "." in text:  # trailing zeros are only insignificant after a decimal point
        text = text.rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def extrusion_lengths(art: Art) -> list:
    """Filament per segment: width x layer height x length / filament area x flow ratio x art flow."""
    factor = art.layer_height / art.machine.filament_area * art.machine.flow_ratio * art.params.flow
    return [w * l * factor for w, l in zip(art.widths, art.lengths())]


def emit(
    art: Art,
    cx: float,
    cy: float,
    z: float,
    relative_e: bool,
    debt_before: float = 0.0,
    e_after: float | None = None,
    pause: bool = False,
    upper_layers: tuple = (),
) -> list:
    """Lines for the art block.

    `debt_before` is how far the filament is retracted on entry. `e_after` is the
    extruder position the following G-code expects, restored here in absolute mode.
    `upper_layers` holds (z, marker comment lines) of further art layers; each retraces
    the previous one backward, so the line only travels where a layer leaves part of it out.
    """
    m = art.machine
    hop = max(m.z_hop, 0.4)
    wanted = max(debt_before, m.retract_length)
    lines = [START_MARK, f"; layer height {_num(art.layer_height, 3)}, speed {_num(art.speed, 1)} mm/s"]
    if not relative_e:
        lines.append("G92 E0")

    position = 0.0  # logical extruder position, absolute mode only

    def move_e(delta: float, feed: float) -> None:
        nonlocal position
        position += delta
        value = delta if relative_e else position
        lines.append(f"G1 E{_num(value, 5)} F{_num(feed * 60, 0)}")

    if wanted > debt_before:
        move_e(-(wanted - debt_before), m.retract_speed)
    lines.append(f"G1 Z{_num(z + hop, 3)} F{Z_FEED}")
    if pause and m.pause_gcode:
        lines.extend(line for line in m.pause_gcode.splitlines() if line.strip())
    x0, y0 = art.points[0]
    lines.append(f"G1 X{_num(cx + x0, 3)} Y{_num(cy + y0, 3)} F{_num(m.travel_speed * 60, 0)}")
    lines.append(f"G1 Z{_num(z, 3)} F{Z_FEED}")
    move_e(wanted, m.deretract_speed)
    lines.append(f"G1 F{_num(art.speed * 60, 0)}")

    # Rounded running total, so rounding never accumulates into a length error.
    exact = position
    written = position
    points, amounts = art.points, extrusion_lengths(art)

    def draw(start: int, end: int) -> None:
        nonlocal exact, written
        step = 1 if end > start else -1
        for index in range(start, end, step):
            exact += amounts[min(index, index + step)]
            rounded = round(exact, 5)
            value = rounded - written if relative_e else rounded
            written = rounded
            x, y = points[index + step]
            lines.append(f"G1 X{_num(cx + x, 3)} Y{_num(cy + y, 3)} E{_num(value, 5)}")

    def cross_to(index: int, layer_z: float) -> None:
        """Lifts over everything printed so far, moves to a run's start and primes."""
        nonlocal position
        position = written
        move_e(-m.retract_length, m.retract_speed)
        lines.append(f"G1 Z{_num(layer_z + hop, 3)} F{Z_FEED}")
        x, y = points[index]
        lines.append(f"G1 X{_num(cx + x, 3)} Y{_num(cy + y, 3)} F{_num(m.travel_speed * 60, 0)}")
        lines.append(f"G1 Z{_num(layer_z, 3)} F{Z_FEED}")
        move_e(m.retract_length, m.deretract_speed)
        lines.append(f"G1 F{_num(art.speed * 60, 0)}")

    levels = [(z, ())] + list(upper_layers)
    nozzle_z = z
    at = 0
    for (layer_z, markers), runs in zip(levels, art.drawn_layers(len(levels))):
        lines.extend(markers)
        for start, end in runs:
            if start != at:
                cross_to(start, layer_z)
            elif layer_z != nozzle_z:
                lines.append(f"G1 Z{_num(layer_z, 3)} F{Z_FEED}")
                lines.append(f"G1 F{_num(art.speed * 60, 0)}")
            nozzle_z = layer_z
            draw(start, end)
            at = end

    top_z = levels[-1][0]
    position = written
    move_e(-m.retract_length, m.retract_speed)
    lines.append(f"G1 Z{_num(top_z + hop, 3)} F{Z_FEED}")
    if not relative_e and e_after is not None:
        lines.append(f"G92 E{_num(e_after, 5)}")
    lines.append(END_MARK)
    return lines
