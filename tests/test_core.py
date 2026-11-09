"""Invariants on generated paths and G-code. No orca import in the code under test."""
import base64
import math
import re
from dataclasses import replace
from pathlib import Path

import pytest

from core import art as A, gcode, pipeline, preview, splice, toolpath
from core.gcode import END_MARK, START_MARK
from core.image import GrayImage, step_image, tone

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "golden_preview.bin"
MACHINE = A.Machine(max_volumetric=15.0, relative_e=True)
WORD = re.compile(r"([XYZEF])([-+]?[0-9]*\.?[0-9]+)")


def noise(size=64):
    data = bytearray()
    state = 12345
    for _ in range(size * size):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        data.append(state >> 23 & 0xFF)
    return GrayImage(size, size, bytes(data))


def gradient(size=64):
    return GrayImage(size, size, bytes(int(255 * x / (size - 1)) for _ in range(size) for x in range(size)))


PARAMS = A.Params(diameter=40.0, pitch=0.65, width_min=0.24, width_max=0.64, ring=1.0)


def art(params=PARAMS, image=None, machine=MACHINE, layer=0.2):
    return A.build(params, image or noise(), machine, layer)


def parse(block):
    moves = []
    for line in block:
        words = {k: float(v) for k, v in WORD.findall(line.split(";")[0])}
        if line.startswith("G1"):
            moves.append(words)
    return moves


def run(block, relative):
    """Moves from the first positive extrusion on: (x, y, e_delta)."""
    position, previous = 0.0, 0.0
    deltas = []
    x = y = None
    for words in parse(block):
        x = words.get("X", x)
        y = words.get("Y", y)
        if "E" not in words:
            deltas.append((x, y, None, words))
            continue
        delta = words["E"] if relative else words["E"] - position
        position = position + delta if relative else words["E"]
        deltas.append((x, y, delta, words))
    return deltas


def extrusion_section(entries):
    """Entries from the first XY extrusion up to and including the last."""
    moving = [i for i, e in enumerate(entries) if e[2] and e[2] > 0 and ("X" in e[3] or "Y" in e[3])]
    return entries[moving[0] : moving[-1] + 1]


def test_spiral_chord_and_pitch():
    points = toolpath.spiral(20.0, 0.65, 0.5)
    chords = [math.dist(a, b) for a, b in zip(points, points[1:])]
    assert all(c == pytest.approx(0.5, rel=0.03) for c in chords)
    assert all(math.hypot(*p) <= 20.0 + 1e-9 for p in points)
    assert math.hypot(*points[0]) == pytest.approx(0.65, abs=0.01)
    # Radius grows one pitch per turn.
    assert math.hypot(*points[-1]) > 19.5


def test_raster_continuous_and_inside():
    points = toolpath.raster(20.0, 0.65, 0.5)
    chords = [math.dist(a, b) for a, b in zip(points, points[1:])]
    assert max(chords) <= 0.5 + 1e-6
    assert all(math.hypot(*p) <= 20.0 + 1e-9 for p in points)
    assert min(chords) > 0


def test_hilbert_is_one_line_through_every_cell():
    half, pitch, chord = 19.28, 0.3, 0.5
    points = toolpath.hilbert(half, pitch, chord)
    order = toolpath.hilbert_order(half, pitch)
    step = 2 * half / (2**order - 1)
    assert step >= pitch and 2 * half / (2 ** (order + 1) - 1) < pitch
    chords = [(a, b) for a, b in zip(points, points[1:])]
    assert all(0 < math.dist(a, b) <= chord + 1e-6 for a, b in chords)
    assert all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9 for a, b in chords)
    assert all(max(abs(x), abs(y)) <= half + 1e-9 for x, y in points)
    rounded = {(round(x, 5), round(y, 5)) for x, y in points}
    assert len(rounded) == len(points)  # never touches itself
    lattice = {(round(-half + i * step, 5), round(-half + j * step, 5)) for i in range(2**order) for j in range(2**order)}
    assert lattice <= rounded


def test_hilbert_sizes_keep_the_pitch():
    for size in A.hilbert_info(PARAMS)["sizes"]:
        got = A.hilbert_info(replace(PARAMS, mode="hilbert", diameter=size))["pitch"]
        assert PARAMS.pitch <= got < PARAMS.pitch * 1.02


def test_hilbert_needs_room():
    with pytest.raises(ValueError, match="too small"):
        toolpath.hilbert(0.8, 0.65, 0.5)


def test_hilbert_gcode_fills_the_square():
    a = art(replace(PARAMS, mode="hilbert", ring=0.0))
    section = extrusion_section(run(gcode.emit(a, 100.0, 100.0, 1.0, True), True))
    assert all(e[2] > 0 for e in section) and len(section) == len(a.widths)
    assert all(max(abs(x - 100.0), abs(y - 100.0)) <= 20.0 for x, y, _, _ in section)
    assert max(math.hypot(x - 100.0, y - 100.0) for x, y, _, _ in section) > 26.0  # reaches the corners


def test_hilbert_frame_is_full_width():
    p = replace(PARAMS, mode="hilbert", ring=2.0, slew=100.0)
    a = art(p, GrayImage(2, 2, bytes([255] * 4)))
    edge = p.half_span - 2.0
    for ((ax, ay), (bx, by)), width in zip(zip(a.points, a.points[1:]), a.widths):
        if max(abs(ax + bx), abs(ay + by)) / 2 >= edge + 1.0:
            assert width == pytest.approx(p.width_max, abs=0.01)


def test_shape_check():
    top = splice.locate((FIXTURES / "klipper_absolute.gcode").read_text(encoding="utf-8").split("\n"))
    assert top.diagonal == pytest.approx(40.0, abs=1.5)
    splice.check_disc(top, 40.0)
    with pytest.raises(splice.NotPlaceholder, match="square"):
        splice.check_disc(top, 40.0, square=True)
    corners = replace(top, diagonal=56.5)
    splice.check_disc(corners, 40.0, square=True)
    with pytest.raises(splice.NotPlaceholder, match="disc"):
        splice.check_disc(corners, 40.0)


def test_flow_multiplier_scales_extrusion_only():
    plain, more = art(), art(replace(PARAMS, flow=1.1))
    assert more.widths == plain.widths
    for a, b in zip(gcode.extrusion_lengths(plain), gcode.extrusion_lengths(more)):
        assert b == pytest.approx(a * 1.1)
    capped = art(replace(PARAMS, flow=1.5), machine=replace(MACHINE, max_volumetric=2.0))
    assert capped.stats()["max_flow"] <= 2.0 + 1e-9


def test_nozzle_input_sets_the_width_limits():
    with pytest.raises(A.ArtError):
        art(replace(PARAMS, width_max=1.0, pitch=1.0))
    a = art(replace(PARAMS, nozzle=0.6, width_min=0.3, width_max=1.0, pitch=1.0))
    assert a.machine.nozzle == 0.6


@pytest.mark.parametrize("bad", [{"flow": 2.0}, {"art_layers": 0}, {"nozzle": 2.0}, {"layer_height": 0.5}])
def test_new_inputs_are_validated(bad):
    with pytest.raises(A.ArtError):
        art(replace(PARAMS, **bad))


@pytest.mark.parametrize("relative", [True, False])
def test_art_layers_retrace_without_travel(relative):
    a = art(machine=replace(MACHINE, relative_e=relative))
    upper = ((1.2, ["; layer two"]), (1.4, ["; layer three"]))
    block = gcode.emit(a, 100.0, 100.0, 1.0, relative, upper_layers=upper)
    assert "; layer two" in block and "; layer three" in block
    section = [e for e in extrusion_section(run(block, relative)) if "Z" not in e[3] and "X" in e[3]]
    assert len(section) == 3 * len(a.widths)
    n = len(a.widths)
    assert (section[n][0], section[n][1]) == pytest.approx((section[n - 2][0], section[n - 2][1]), abs=1e-3)  # turns straight back
    assert all(e[2] > 0 for e in section)
    assert sum(1 for e in run(block, relative) if e[2] is not None and e[2] < 0) == 2  # still one prime, one retract
    single = sum(gcode.extrusion_lengths(a))
    assert sum(e[2] for e in section) == pytest.approx(3 * single, abs=1e-3)
    zs = [float(l.split("Z")[1].split()[0]) for l in block if l.startswith("G1 Z")]
    assert zs == [1.4, 1.0, 1.2, 1.4, 1.8]


@pytest.mark.parametrize("name", ["bambu_x1c_relative.gcode", "klipper_absolute.gcode"])
def test_two_art_layers_on_real_slices(name):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    lines = text.split("\n")
    one, two = splice.locate(lines), splice.locate(lines, 2)
    assert two.z == pytest.approx(one.z - one.height) and two.region_start < one.region_start
    assert two.region_end == one.region_end and two.size == one.size
    assert [z for z, _ in two.upper] == [one.z]
    assert two.upper[0][1][0].startswith(("; CHANGE_LAYER", ";LAYER_CHANGE"))


def test_too_many_art_layers_is_not_the_placeholder():
    with pytest.raises(splice.NotPlaceholder, match="too few layers"):
        splice.locate((FIXTURES / "klipper_absolute.gcode").read_text(encoding="utf-8").split("\n"), 500)


@pytest.mark.parametrize("change,word", [({"layer_height": 0.16}, "layer height"), ({"nozzle": 0.6, "width_max": 1.0, "pitch": 1.0}, "nozzle")])
def test_slice_refuses_a_mismatch(change, word):
    text = (FIXTURES / "bambu_x1c_relative.gcode").read_text(encoding="utf-8")
    job = pipeline.job_to_dict(replace(PARAMS, **change), noise())
    with pytest.raises(A.ArtError, match=word):
        pipeline.process(text, job, {"nozzle_diameter": "0.4"}.get)


def test_two_filaments_skip_the_pause_and_check_the_tool():
    text = (FIXTURES / "bambu_x1c_relative.gcode").read_text(encoding="utf-8")
    machine_pause = {"machine_pause_gcode": "M400 U1", "nozzle_diameter": "0.4"}
    one = pipeline.process(text, pipeline.job_to_dict(PARAMS, noise()), machine_pause.get)
    assert "M400 U1" in one.text
    with pytest.raises(A.ArtError, match="filament 1"):
        pipeline.process(text, pipeline.job_to_dict(replace(PARAMS, base_filament=2, art_filament=3), noise()), machine_pause.get)
    two = pipeline.process(text, pipeline.job_to_dict(replace(PARAMS, base_filament=2, art_filament=1), noise()), machine_pause.get)
    assert two.changed and "M400 U1" not in two.text.split(START_MARK)[1].split(END_MARK)[0]


def test_tone():
    assert tone(0.5, 1, 1) == pytest.approx(0.5)
    assert tone(0.5, 1, 2) == pytest.approx(0.25)
    assert tone(0.0, 2, 1) == 0.0
    assert tone(1.0, 2, 1) == 1.0


def test_step_image_covers_range():
    image = step_image(8)
    assert image.sample(0, 0.5) == pytest.approx(0)
    assert image.sample(1, 0.5) == pytest.approx(1)


def test_center_square():
    assert GrayImage(4, 2, bytes(range(8))).center_square().data == bytes([1, 2, 5, 6])


@pytest.mark.parametrize("mode", A.MODES)
def test_width_range_and_slew(mode):
    a = art(replace(PARAMS, mode=mode, ring=0.0))
    lengths = a.lengths()
    assert len(a.widths) == len(a.points) - 1
    assert min(a.widths) >= PARAMS.width_min - 1e-9
    assert max(a.widths) <= PARAMS.width_max + 1e-9
    for i in range(1, len(a.widths)):
        assert abs(a.widths[i] - a.widths[i - 1]) <= PARAMS.slew * max(lengths[i], lengths[i - 1]) + 1e-9


def test_darker_is_wider_and_invert_flips():
    black = GrayImage(2, 2, bytes(4))
    white = GrayImage(2, 2, bytes([255] * 4))
    p = replace(PARAMS, ring=0.0)
    assert sum(art(p, black).widths) > sum(art(p, white).widths)
    inverted = replace(p, invert=True)
    assert sum(art(inverted, black).widths) < sum(art(inverted, white).widths)


def test_ring_is_full_width():
    a = art(replace(PARAMS, ring=2.0), GrayImage(2, 2, bytes([255] * 4)))
    assert a.widths[-1] == pytest.approx(PARAMS.width_max, abs=0.05)


def test_flow_cap_lowers_speed():
    machine = replace(MACHINE, max_volumetric=2.0)
    a = art(machine=machine)
    assert max(a.widths) * 0.2 * a.speed <= 2.0 + 1e-9
    assert a.speed == pytest.approx(2.0 / (0.64 * 0.2))


@pytest.mark.parametrize("relative", [True, False])
def test_gcode_invariants(relative):
    a = art(machine=replace(MACHINE, relative_e=relative))
    block = gcode.emit(a, 100.0, 100.0, 1.0, relative, e_after=7.5)
    assert block[0] == START_MARK and block[-1] == END_MARK
    if not relative:
        assert block[-2] == "G92 E7.5"
    entries = run(block, relative)
    section = extrusion_section(entries)
    # One run: every move between the first and last extrusion extrudes, no travel or retraction.
    assert all(e[2] is not None and e[2] > 0 for e in section)
    assert len(section) == len(a.widths)
    # Exactly one priming move at the run's start, one retraction at its end.
    assert sum(1 for e in entries if e[2] is not None and e[2] < 0) == 2
    # Inside the disc and on the layer.
    for x, y, _, _ in section:
        assert math.hypot(x - 100.0, y - 100.0) <= 20.0
    # Each extrusion's length matches width x height x length / area.
    expected = gcode.extrusion_lengths(a)
    for entry, amount in zip(section, expected):
        assert entry[2] == pytest.approx(amount, abs=2e-5)


def test_absolute_and_relative_extrude_the_same():
    relative = sum(e[2] for e in extrusion_section(run(gcode.emit(art(), 0, 0, 1.0, True), True)))
    absolute = sum(e[2] for e in extrusion_section(run(gcode.emit(art(), 0, 0, 1.0, False), False)))
    assert relative == pytest.approx(absolute, abs=1e-4)


def test_pause_goes_before_travel():
    machine = replace(MACHINE, pause_gcode="M400 U1")
    block = gcode.emit(art(machine=machine), 100, 100, 1.0, True, pause=True)
    assert block.index("M400 U1") < next(i for i, l in enumerate(block) if l.startswith("G1 X"))
    assert "M400 U1" not in gcode.emit(art(machine=machine), 100, 100, 1.0, True, pause=False)


def test_validation():
    with pytest.raises(A.ArtError):
        art(replace(PARAMS, width_min=0.1))
    with pytest.raises(A.ArtError):
        art(replace(PARAMS, width_max=0.9))
    with pytest.raises(A.ArtError):
        art(replace(PARAMS, width_max=0.8, pitch=0.5))
    with pytest.raises(A.ArtError):
        A.build(PARAMS, None, MACHINE, 0.2)


def test_gamma_from_step():
    assert A.gamma_from_step(3, 7) == pytest.approx(1.0)
    assert A.gamma_from_step(2, 7) > 1.0  # dark mid-gray step needs a darker tone curve
    with pytest.raises(A.ArtError):
        A.gamma_from_step(0, 7)


def test_machine_from_config():
    values = {
        "nozzle_diameter": "0.6", "filament_diameter": "1.75,2.85", "printable_area": "0x0,200x0,200x180,0x180",
        "use_relative_e_distances": "0", "machine_pause_gcode": "PAUSE\\nM400",
    }
    m = A.machine_from_config(values.get, tool=1)
    assert m.nozzle == 0.6 and m.filament_diameter == 2.85 and m.bed == (0, 0, 200, 180) and not m.relative_e
    assert m.pause_gcode == "PAUSE\nM400"


@pytest.mark.parametrize("name,z,height,relative", [
    ("bambu_x1c_relative.gcode", 1.0, 0.2, True),
    ("klipper_absolute.gcode", 1.0, 0.2, False),
])
def test_locate_real_slices(name, z, height, relative):
    lines = (FIXTURES / name).read_text(encoding="utf-8").split("\n")
    top = splice.locate(lines)
    assert top.z == z and top.height == height and top.relative_e is relative
    assert top.size == pytest.approx((40.0, 40.0), abs=1.0)
    # The disc is placed by the slicer; its centre is somewhere on the bed.
    assert 20 < top.center[0] < 230 and 20 < top.center[1] < 230


def test_real_slice_end_to_end():
    text = (FIXTURES / "klipper_absolute.gcode").read_text(encoding="utf-8")
    config = {"use_relative_e_distances": "0", "printable_area": "0x0,250x0,250x250,0x250", "layer_height": "0.2"}
    job = pipeline.job_to_dict(PARAMS, noise())
    outcome = pipeline.process(text, job, config.get)
    assert outcome.changed
    lines = outcome.text.split("\n")
    start, end = lines.index(START_MARK), lines.index(END_MARK)
    top = splice.locate(text.split("\n"))
    block = lines[start : end + 1]
    assert block[1].startswith("; layer height 0.2")
    assert "; Z_" not in "".join(block)
    assert block[-2].startswith("G92 E")
    # The following G-code is the original tail.
    assert lines[end + 1] == text.split("\n")[top.region_end]
    assert splice.is_done(outcome.text)
    assert pipeline.process(outcome.text, job, config.get).text == outcome.text


def test_mismatched_disc_untouched():
    text = (FIXTURES / "bambu_x1c_relative.gcode").read_text(encoding="utf-8")
    job = pipeline.job_to_dict(replace(PARAMS, diameter=60.0), noise())
    outcome = pipeline.process(text, job, {}.get)
    assert not outcome.changed and outcome.text == text


def test_bed_check():
    text = (FIXTURES / "bambu_x1c_relative.gcode").read_text(encoding="utf-8")
    job = pipeline.job_to_dict(PARAMS, noise())
    with pytest.raises(ValueError, match="printable area"):
        pipeline.process(text, job, {"printable_area": "0x0,10x0,10x10,0x10"}.get)


def test_golden_preview():
    rendered = preview.render(art(image=gradient()), 200)
    if not GOLDEN.exists():
        GOLDEN.write_bytes(rendered)
        pytest.skip("golden file written; run again")
    golden = GOLDEN.read_bytes()
    assert len(rendered) == len(golden)
    assert sum(abs(a - b) for a, b in zip(rendered, golden)) / len(golden) < 1.0


def test_feedrates_are_mm_per_minute():
    machine = replace(MACHINE, retract_speed=30.0, deretract_speed=30.0, travel_speed=500.0)
    block = gcode.emit(art(machine=machine), 100, 100, 1.0, True)
    feeds = [m["F"] for m in parse(block) if "F" in m]
    assert 1800 in feeds and 30000 in feeds and 2400 in feeds  # retract, travel, 40 mm/s print
    assert min(feeds) >= 1200
