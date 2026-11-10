"""Invariants on generated paths and G-code. No orca import in the code under test."""
import base64
import io
import math
import re
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from core import art as A, gcode, pipeline, placeholder, preview, relief, shape, splice, tone_prep, toolpath
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
    splice.check_shape(top, shape.make("circle", 40.0, 40.0))
    with pytest.raises(splice.NotPlaceholder, match="square"):
        splice.check_shape(top, shape.make("square", 40.0, 40.0))
    corners = replace(top, diagonal=56.5)
    splice.check_shape(corners, shape.make("square", 40.0, 40.0))
    with pytest.raises(splice.NotPlaceholder, match="disc"):
        splice.check_shape(corners, shape.make("circle", 40.0, 40.0))


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
    a = art(replace(PARAMS, mode=mode, ring=0.0, art_layers=2))
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
    # The disc is placed by the slicer; its center is somewhere on the bed.
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


RELIEF = replace(PARAMS, mode="relief", art_layers=3, ring=0.0, slew=0.5)


def half_dark(size=64):
    """Black on the left half, white on the right: long runs, far apart."""
    return GrayImage(size, size, bytes(0 if x < size / 2 else 255 for _ in range(size) for x in range(size)))


def white(size=64):
    return GrayImage(size, size, bytes([255]) * (size * size))


def relief_layers(block):
    """XY extrusion moves of each layer of a relief block, split at its Z changes."""
    layers, z, x, y = {}, None, None, None
    for words in parse(block):
        z = words.get("Z", z)
        nx, ny = words.get("X", x), words.get("Y", y)
        if words.get("E", 0) > 0 and ("X" in words or "Y" in words):
            layers.setdefault(z, []).append(((x, y), (nx, ny)))
        x, y = nx, ny
    return layers


def as_relative(block, relative):
    """The same block with E written relatively, so tests read one form."""
    if relative:
        return block
    lines, position = [], 0.0
    for line in block:
        match = re.search(r"\bE([-+]?[0-9.]+)", line)
        if line.startswith("G1") and match:
            value = float(match.group(1))
            line = line[: match.start(1)] + f"{value - position:.5f}" + line[match.end(1) :]
            position = value
        lines.append(line)
    return lines


def mesh_objects(archive_bytes):
    """Vertices and triangles of each mesh in a generated 3MF."""
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        model = archive.read("3D/Objects/flow_line_art_disc.model").decode()
    meshes = []
    for body in re.findall(r"<mesh>(.*?)</mesh>", model):
        vertices = re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"/>', body)
        triangles = [tuple(map(int, t)) for t in re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"/>', body)]
        meshes.append((vertices, triangles))
    return meshes


@pytest.mark.parametrize("square", [False, True])
def test_two_part_file_shares_vertices_so_each_part_is_closed(square):
    """The 3MF route keeps vertices as written, and the slicer joins triangles through shared ones."""
    rim = shape.make("square" if square else "circle", 42.4, 42.4).outline()
    meshes = mesh_objects(placeholder.two_filament_3mf(rim, 0.8, 1.4, 1, 2, (128.0, 128.0), "2.5.0"))
    assert len(meshes) == 2
    for vertices, triangles in meshes:
        assert len(set(vertices)) == len(vertices)
        edges = Counter(edge for a, b, c in triangles for edge in ((a, b), (b, c), (c, a)))
        assert all(count == 1 and edges[(end, start)] == 1 for (start, end), count in edges.items())


def test_relief_passes_follow_the_tone():
    a = art(RELIEF, half_dark())
    assert len(a.passes) == len(a.widths) and set(a.passes) == {1, 2, 3}
    assert max(zip(a.widths, a.passes))[1] == 3 and min(zip(a.widths, a.passes))[1] == 1


def test_plain_modes_have_no_pass_counts():
    assert art().passes is None


@pytest.mark.parametrize("layers", [1, 7])
def test_relief_layer_count_is_limited(layers):
    with pytest.raises(A.ArtError, match="Relief"):
        art(replace(RELIEF, art_layers=layers), half_dark())


def test_relief_drops_short_runs_and_fills_short_gaps():
    lengths = [1.0] * 40
    full, none = 0.64, 0.24
    blip = [none] * 10 + [full] * 3 + [none] * 27  # 3 mm is too short to be worth a stop
    assert set(relief.pass_counts(blip, lengths, none, full, 2)) == {1}
    hole = [none] * 5 + [full] * 12 + [none] * 3 + [full] * 15 + [none] * 5  # nor is a 3 mm gap
    assert relief.runs([c >= 2 for c in relief.pass_counts(hole, lengths, none, full, 2)]) == [(5, 35)]


def test_relief_upper_passes_stand_on_lower_ones():
    a = art(RELIEF, noise())
    assert all(a.passes[i] >= 2 for i, c in enumerate(a.passes) if c >= 3)
    lengths = a.lengths()
    for level in (2, 3):
        for start, end in relief.runs([c >= level for c in a.passes]):
            assert sum(lengths[start:end]) >= relief.MIN_RUN_MM


@pytest.mark.parametrize("relative", [True, False])
def test_relief_first_layer_is_one_unbroken_line(relative):
    a = art(RELIEF, half_dark(), machine=replace(MACHINE, relative_e=relative))
    block = gcode.emit(a, 100.0, 100.0, 1.0, relative, upper_layers=((1.2, ["; two"]), (1.4, ["; three"])))
    first = relief_layers(as_relative(block, relative))[1.0]
    assert len(first) == len(a.widths)
    assert all(one[1] == two[0] for one, two in zip(first, first[1:]))


def test_relief_upper_layers_only_cover_dark_runs():
    a = art(RELIEF, half_dark())
    block = gcode.emit(a, 0.0, 0.0, 1.0, True, upper_layers=((1.2, ["; two"]), (1.4, ["; three"])))
    layers = relief_layers(block)
    assert 0 < len(layers[1.4]) <= len(layers[1.2]) < len(layers[1.0])
    assert {pair[0] for pair in layers[1.4]} <= {p for pair in layers[1.2] for p in pair}
    # The dark half is on the left; the width limit lets a run reach a little past the middle.
    assert all((start[0] + end[0]) / 2 < 3.0 for start, end in layers[1.2] + layers[1.4])


@pytest.mark.parametrize("relative", [True, False])
def test_relief_stops_retract_lift_and_prime_evenly(relative):
    a = art(RELIEF, half_dark(), machine=replace(MACHINE, relative_e=relative))
    block = gcode.emit(a, 100.0, 100.0, 1.0, relative, upper_layers=((1.2, ["; two"]), (1.4, ["; three"])))
    stops = a.stats()["stops"]
    assert stops > 0
    entries = run(block, relative)
    assert sum(1 for e in entries if e[2] is not None and e[2] < 0) == stops + 2  # opening and closing retracts too
    drawn = sum(amount * count for amount, count in zip(gcode.extrusion_lengths(a), a.passes))
    assert sum(e[2] for e in entries if e[2] is not None) == pytest.approx(drawn - MACHINE.retract_length, abs=1e-3)
    z = None
    for line in block:
        words = {k: float(v) for k, v in WORD.findall(line.split(";")[0])}
        z = words.get("Z", z)
        if "X" in words and "E" not in words:
            assert z >= 1.0 + 0.4 - 1e-6  # every travel happens lifted


def test_relief_keeps_layer_markers_when_a_layer_is_empty():
    a = art(RELIEF, white())
    assert set(a.passes) == {1}
    block = gcode.emit(a, 0.0, 0.0, 1.0, True, upper_layers=((1.2, ["; two"]), (1.4, ["; three"])))
    assert "; two" in block and "; three" in block
    assert a.stats()["stops"] == 0


def test_relief_stats_count_only_what_is_printed():
    a = art(RELIEF, half_dark())
    stats = a.stats()
    lengths = a.lengths()
    printed = sum(l * c for l, c in zip(lengths, a.passes))
    assert stats["length_mm"] == pytest.approx(printed)
    assert stats["time_s"] == pytest.approx(printed / a.speed + stats["stops"] * relief.SECONDS_PER_STOP)
    assert sum(lengths) < stats["length_mm"] < 3 * sum(lengths)


def test_relief_preview_shows_the_height_steps():
    raised = preview.render(art(RELIEF, half_dark()), 200)
    flat = preview.render(art(replace(RELIEF, mode="spiral", art_layers=1), half_dark()), 200)
    assert len(raised) == len(flat) == 200 * 200
    assert sum(a < b for a, b in zip(raised, flat)) > 50  # the lit side
    assert sum(a > b for a, b in zip(raised, flat)) > 50  # the shaded side


def test_job_carries_mode_and_format_version():
    job = pipeline.job_to_dict(RELIEF, half_dark())
    assert job["mode"] == "relief" and job["version"] == pipeline.JOB_FORMAT_VERSION
    params, image = pipeline.job_from_dict(job)
    assert params.mode == "relief" and image is not None


@pytest.mark.parametrize("name", ["bambu_x1c_relative.gcode", "klipper_absolute.gcode"])
def test_relief_on_real_slices(name):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    config = {}
    for line in text.splitlines():
        match = re.match(r"^; ([a-z_0-9]+) = (.*)$", line)
        if match:
            config.setdefault(match.group(1), match.group(2))
    lines = text.split("\n")
    top = splice.locate(lines, 3)
    params = replace(RELIEF, diameter=round(sum(top.size) / 2))
    outcome = pipeline.process(text, pipeline.job_to_dict(params, half_dark()), config.get)
    assert outcome.changed and "stops" in outcome.message
    result = outcome.text.split("\n")
    start, end = result.index(START_MARK), result.index(END_MARK)
    assert result[:start] == lines[: top.region_start] and result[end + 1 :] == lines[top.region_end :]
    marks = ("; CHANGE_LAYER", ";LAYER_CHANGE")
    assert sum(line.startswith(marks) for line in result) == sum(line.startswith(marks) for line in lines)


def percentile_of(image, fraction):
    return sorted(image.data)[int(len(image.data) * fraction)]


def narrow_gradient(low=100, high=150, size=64):
    return GrayImage(size, size, bytes(low + (high - low) * x // (size - 1) for _ in range(size) for x in range(size)))


def test_tone_preparation_stretches_a_flat_looking_picture():
    prepared = tone_prep.prepare(narrow_gradient())
    assert (prepared.width, prepared.height) == (64, 64)
    assert percentile_of(prepared, 0.02) < 20 and percentile_of(prepared, 0.98) > 235


def test_tone_preparation_ignores_a_few_extreme_pixels():
    data = bytearray(narrow_gradient().data)
    data[0], data[1] = 0, 255
    prepared = tone_prep.prepare(GrayImage(64, 64, bytes(data)))
    assert percentile_of(prepared, 0.02) < 20 and percentile_of(prepared, 0.98) > 235


def test_tone_preparation_leaves_a_blank_picture_alone():
    blank = GrayImage(32, 32, bytes([128]) * (32 * 32))
    assert tone_prep.prepare(blank) == blank


def test_tone_preparation_brings_the_middle_to_its_target():
    prepared = tone_prep.prepare(narrow_gradient(60, 140))
    assert percentile_of(prepared, 0.5) == pytest.approx(255 * tone_prep.MIDTONE_TARGET, abs=8)


def test_inverted_picture_gets_the_mirrored_middle():
    prepared = tone_prep.prepare(narrow_gradient(60, 140), inverted=True)
    assert percentile_of(prepared, 0.5) == pytest.approx(255 * (1 - tone_prep.MIDTONE_TARGET), abs=8)


def test_sharpening_raises_contrast_at_an_edge_only():
    size = 80
    step = GrayImage(size, size, bytes(100 if x < size / 2 else 160 for _ in range(size) for x in range(size)))
    sharp = tone_prep.sharpen(step)
    row = sharp.data[size * 40 : size * 41]
    assert row[39] < 100 and row[40] > 160
    assert row[2] == 100 and row[size - 3] == 160


def test_auto_tone_is_off_unless_asked_for():
    assert A.Params().auto_tone is False


def test_auto_tone_spends_more_of_the_width_range():
    plain = art(PARAMS, narrow_gradient())
    toned = art(replace(PARAMS, auto_tone=True), narrow_gradient())
    assert max(toned.widths) - min(toned.widths) > max(plain.widths) - min(plain.widths) + 0.1


def test_auto_tone_leaves_calibration_alone():
    calibration = replace(PARAMS, mode="calibration")
    assert art(calibration).widths == art(replace(calibration, auto_tone=True)).widths


def test_a_job_saved_before_auto_tone_stays_off():
    job = pipeline.job_to_dict(PARAMS, noise())
    del job["params"]["auto_tone"]
    params, image = pipeline.job_from_dict(job)
    assert params.auto_tone is False
    assert A.build(params, image, MACHINE, 0.2).widths == art(PARAMS, noise()).widths


def test_a_new_job_keeps_auto_tone():
    params, _image = pipeline.job_from_dict(pipeline.job_to_dict(replace(PARAMS, auto_tone=True), noise()))
    assert params.auto_tone is True


def test_a_saved_job_past_the_slider_limits_still_builds():
    params = replace(PARAMS, contrast=5.0, gamma=4.0)
    outcome_widths = A.build(params, noise(), MACHINE, 0.2).widths
    assert len(outcome_widths) > 0


SHAPE_SIZES = {"square": (60, 60), "circle": (60, 60), "rectangle": (80, 50), "oval": (80, 50), "hexagon": (60, 60)}


def make_shape(name):
    return shape.make(name, *SHAPE_SIZES[name])


def shaped(mode, name, **extra):
    width, height = SHAPE_SIZES[name]
    return replace(PARAMS, mode=mode, shape=name, width=width, height=height, ring=0.0, **extra)


def outline_box(polygon):
    xs, ys = zip(*polygon)
    return max(xs) - min(xs), max(ys) - min(ys)


@pytest.mark.parametrize("name,size", [("circle", (60, 60)), ("square", (60, 60)), ("rectangle", (80, 50)), ("oval", (80, 50)), ("hexagon", (60, 60 * math.sqrt(3) / 2))])
def test_outline_has_the_asked_size(name, size):
    assert outline_box(make_shape(name).outline()) == pytest.approx(size, abs=0.02)


@pytest.mark.parametrize("name", shape.NAMES)
def test_inset_is_positive_inside_and_negative_outside(name):
    s = make_shape(name)
    assert s.inset(0.0, 0.0) > 0
    assert s.inset(1000.0, 0.0) < 0 and s.inset(0.0, -1000.0) < 0


@pytest.mark.parametrize("name", ["rectangle", "oval", "hexagon"])
def test_row_span_stays_inside_by_the_inset(name):
    s = make_shape(name)
    left, right = s.row_span(3.0, 1.0)
    assert left < right
    assert s.inset(left + 0.01, 3.0) >= 1.0 - 0.1 and s.inset(right - 0.01, 3.0) >= 1.0 - 0.1


def test_row_span_is_none_past_the_top():
    assert make_shape("hexagon").row_span(100.0, 0.0) is None


def test_every_mode_lists_its_shapes():
    table = shape.SHAPES_BY_MODE
    assert set(table) == set(A.MODES)
    assert table["raster"] == shape.NAMES
    assert table["spiral"] == table["relief"] == ("square", "circle", "rectangle")
    assert table["hilbert"] == ("square",)
    assert table["calibration"] == ("circle",)


@pytest.mark.parametrize("mode,name", [("spiral", "oval"), ("relief", "hexagon"), ("hilbert", "circle"), ("hilbert", "rectangle"), ("calibration", "square")])
def test_a_mode_refuses_a_shape_it_cannot_do_well(mode, name):
    with pytest.raises(A.ArtError):
        art(replace(shaped(mode, name), art_layers=3 if mode == "relief" else 1))


def test_rectangular_spiral_is_one_line_with_even_spacing():
    points = toolpath.rectangular_spiral(30.0, 20.0, 0.65, 0.5)
    assert all(math.dist(a, b) <= 0.5 + 1e-6 for a, b in zip(points, points[1:]))
    assert all(abs(x) <= 30.0 + 1e-6 and abs(y) <= 20.0 + 1e-6 for x, y in points)
    assert math.hypot(*points[0]) < math.hypot(*points[-1])  # from the middle outward, like the round spiral
    rights = sorted({round(y, 3) for x, y in points if x > 0 and abs(y) < 0.5 and abs(x) > 15})
    columns = sorted({round(x, 3) for x, y in points if abs(y) < 0.3 and x > 15})
    assert all(b - a == pytest.approx(0.65, abs=0.01) for a, b in zip(columns, columns[1:]))
    assert rights


@pytest.mark.parametrize("name", shape.NAMES)
def test_zigzag_stays_inside_every_shape(name):
    a = art(shaped("raster", name))
    s = make_shape(name)
    edge = PARAMS.margin + PARAMS.width_max / 2
    assert all(s.inset(x, y) >= edge - 0.15 for x, y in a.points)
    assert all(math.dist(p, q) <= PARAMS.chord + 1e-6 for p, q in zip(a.points, a.points[1:]))


@pytest.mark.parametrize("name", ["square", "rectangle"])
@pytest.mark.parametrize("mode", ["spiral", "relief"])
def test_spiral_modes_fill_their_box(mode, name):
    a = art(replace(shaped(mode, name), art_layers=3 if mode == "relief" else 1))
    width, height = SHAPE_SIZES[name]
    xs, ys = zip(*a.points)
    edge = PARAMS.margin + PARAMS.width_max / 2
    assert max(xs) == pytest.approx(width / 2 - edge, abs=0.01) and max(ys) == pytest.approx(height / 2 - edge, abs=0.01)


def test_a_job_without_a_shape_keeps_its_old_outline():
    assert A.Params(mode="spiral", diameter=50.0).outline == shape.make("circle", 50.0, 50.0)
    assert A.Params(mode="hilbert", diameter=42.4).outline == shape.make("square", 42.4, 42.4)


@pytest.mark.parametrize("mode", ["spiral", "raster"])
def test_a_new_circle_job_matches_a_job_without_a_shape(mode):
    legacy = art(replace(PARAMS, mode=mode))
    named = art(replace(PARAMS, mode=mode, shape="circle", width=PARAMS.diameter, height=PARAMS.diameter))
    assert legacy.points == named.points and legacy.widths == named.widths


def test_picture_is_cut_to_the_shape_not_squeezed():
    wide = GrayImage(4, 2, bytes([0, 10, 20, 30, 40, 50, 60, 70]))
    assert wide.center_crop(1.0) == wide.center_square()
    assert wide.center_crop(2.0) == wide
    tall = wide.center_crop(0.5)
    assert (tall.width, tall.height) == (1, 2)


def test_rectangle_samples_the_whole_picture_width():
    size = 64
    left_dark = GrayImage(size, size, bytes(0 if x < size / 2 else 255 for _ in range(size) for x in range(size)))
    a = art(shaped("raster", "rectangle", slew=5.0), left_dark)
    middles = [((p[0] + q[0]) / 2, w) for p, q, w in zip(a.points, a.points[1:], a.widths)]
    assert sum(w for x, w in middles if x < -5) / sum(1 for x, w in middles if x < -5) > 0.55
    assert sum(w for x, w in middles if x > 5) / sum(1 for x, w in middles if x > 5) < 0.35


def test_shape_must_be_known_and_big_enough():
    with pytest.raises(A.ArtError):
        art(replace(shaped("raster", "circle"), shape="star"))
    with pytest.raises(A.ArtError):
        art(replace(shaped("raster", "rectangle"), height=5.0))


def top_layer_like(s):
    polygon = s.outline()
    xs, ys = zip(*polygon)
    sums = [x + y for x, y in polygon]
    diffs = [x - y for x, y in polygon]
    return splice.TopLayer(1.0, 0.2, 0, 1, (100.0, 100.0), (max(xs) - min(xs), max(ys) - min(ys)), max(max(sums) - min(sums), max(diffs) - min(diffs)) / math.sqrt(2), (), True, 0, 0.0, 0.0)


@pytest.mark.parametrize("name", shape.NAMES)
def test_check_shape_accepts_its_own_outline(name):
    splice.check_shape(top_layer_like(make_shape(name)), make_shape(name))


@pytest.mark.parametrize("real,asked", [("rectangle", "oval"), ("oval", "rectangle"), ("circle", "square"), ("square", "circle"), ("circle", "hexagon"), ("hexagon", "circle")])
def test_check_shape_tells_shapes_apart(real, asked):
    with pytest.raises(splice.NotPlaceholder):
        splice.check_shape(top_layer_like(make_shape(real)), make_shape(asked))


def test_bed_check_uses_both_sides():
    machine = replace(MACHINE, bed=(0.0, 0.0, 100.0, 60.0))
    top = replace(top_layer_like(make_shape("rectangle")), center=(50.0, 30.0))
    splice.check_bed(top, shape.make("rectangle", 80.0, 50.0), machine)
    with pytest.raises(ValueError):
        splice.check_bed(top, shape.make("rectangle", 50.0, 80.0), machine)


@pytest.mark.parametrize("name", shape.NAMES)
def test_base_files_match_the_shape(name):
    s = make_shape(name)
    stl = placeholder.base_stl(s.outline(), 1.4)
    count = int.from_bytes(stl[80:84], "little")
    assert count == 4 * len(s.outline())
    meshes = mesh_objects(placeholder.two_filament_3mf(s.outline(), 0.8, 1.4, 1, 2, (128.0, 128.0), "2.5.0"))
    for vertices, triangles in meshes:
        edges = Counter(edge for a, b, c in triangles for edge in ((a, b), (b, c), (c, a)))
        assert all(count == 1 and edges[(end, start)] == 1 for (start, end), count in edges.items())
        xs = [float(v[0]) for v in vertices]
        assert max(xs) - min(xs) == pytest.approx(SHAPE_SIZES[name][0], abs=0.02)


def test_job_format_records_the_shape():
    job = pipeline.job_to_dict(shaped("raster", "rectangle"), noise())
    assert job["version"] == 3 and job["params"]["shape"] == "rectangle"
    assert job["params"]["width"] == 80 and job["params"]["height"] == 50


def test_shape_list_and_its_order():
    assert shape.NAMES == ("square", "circle", "rectangle", "oval", "hexagon")


def test_saved_job_with_a_removed_shape_is_refused_clearly():
    text = (FIXTURES / "bambu_x1c_relative.gcode").read_text(encoding="utf-8")
    job = pipeline.job_to_dict(replace(shaped("raster", "rectangle"), shape="rounded_rectangle"), noise())
    with pytest.raises(A.ArtError, match="Unknown shape: rounded_rectangle"):
        pipeline.process(text, job, {}.get)
