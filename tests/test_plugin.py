"""Runs against tools/orca_mock: a strict stand-in, not OrcaSlicer itself."""
import base64
import json
import math
import re
import zipfile
from pathlib import Path

import pytest
from orca import harness
import orca

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "src" / "flow_line_art"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
BAMBU = FIXTURES / "bambu_x1c_relative.gcode"
KLIPPER = FIXTURES / "klipper_absolute.gcode"
PAGE = "Flow Line Art"
SLICING = "Flow Line Art G-code"


@pytest.fixture(autouse=True)
def clean():
    harness.reset()
    yield


@pytest.fixture
def loaded():
    return harness.load(ENTRY)


def config_for(path):
    """The resolved config OrcaSlicer wrote at the end of a real sliced file."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^; ([a-z_0-9]+) = (.*)$", line)
        if match:
            values.setdefault(match.group(1), match.group(2))
    return values


def gradient(size=32):
    data = bytes(int(255 * x / (size - 1)) for _ in range(size) for x in range(size))
    return {"width": size, "height": size, "data": base64.b64encode(data).decode()}


def params(**extra):
    base = {"diameter": 40.0, "pitch": 0.65, "width_min": 0.24, "width_max": 0.64, "ring": 1.0}
    base.update(extra)
    return base


def page_call(loaded, data):
    with harness._callback():
        loaded.capability(PAGE).on_message(data)
    return harness.posted[-1]


def save_job(loaded, config, monkeypatch=None, on_plate=False, added=True, **extra):
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    objects = []
    if on_plate:
        objects.append(harness.fake("orca.host.ModelObject", name="flow_line_art_disc.stl", input_file=r"C:\x\flow_line_art_disc.stl"))
    harness.set_host(model=lambda: harness.fake("orca.host.Model", objects=lambda: objects))
    sent = []

    def fake_add(path):
        sent.append(path)
        return added

    loaded.module.plate.add_to_plate = fake_add
    message = {"cmd": "save", "params": params(**extra), "image": gradient()}
    reply = page_call(loaded, message)
    reply["sent"] = sent
    return reply


def test_save_adds_disc_to_plate(loaded):
    reply = save_job(loaded, config_for(BAMBU))
    assert reply["plate"] == "added" and reply["sent"] == [reply["stl"]]


def test_save_does_not_duplicate_disc(loaded):
    config = config_for(BAMBU)
    save_job(loaded, config)
    reply = save_job(loaded, config, on_plate=True)
    assert reply["plate"] == "present" and reply["sent"] == []


def test_save_reports_stale_disc(loaded):
    config = config_for(BAMBU)
    save_job(loaded, config)
    reply = save_job(loaded, config, on_plate=True, diameter=50.0)
    assert reply["plate"] == "stale" and reply["sent"] == []


def test_save_falls_back_to_manual(loaded):
    reply = save_job(loaded, config_for(BAMBU), added=False)
    assert reply["plate"] == "manual"


def test_command_line_escaping(loaded):
    escape = loaded.module.plate.escape_command_line
    assert escape(["orca-slicer", r"C:\a b\c.stl"]) == r'orca-slicer;"C:\\a b\\c.stl"'
    assert escape(["x;y", 'q"r']) == r'"x;y";"q\"r"'


def test_registers_capabilities(loaded):
    assert sorted(c.get_name() for c in loaded.capabilities) == [PAGE, SLICING]


def test_tab_icon_points_at_a_packaged_svg(loaded):
    icon = loaded.capability(PAGE).get_icon()
    assert icon.endswith("/icon.svg") and "\\" not in icon
    assert Path(icon).is_file() and Path(icon).read_text(encoding="utf-8").startswith("<svg")


def test_page_has_every_field_and_the_shared_style(loaded):
    PAGE_HTML = loaded.capability(PAGE).get_ui()
    assert "/*ONELINE_CSS*/" not in PAGE_HTML and "--ol-surface" in PAGE_HTML
    fields = re.search(r"var fields = \[(.*?)\]", PAGE_HTML).group(1)
    for name in re.findall(r'"(\w+)"', fields):
        assert f'id="{name}"' in PAGE_HTML


def test_state_reports_what_the_presets_say(loaded):
    config = two_filament_config()
    config["slicing_pipeline_plugin"] = "Flow Line Art G-code"
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "state"})
    assert reply["type"] == "state" and reply["selected"] is True
    assert reply["printer"]["nozzle"] == pytest.approx(0.4) and reply["printer"]["layer_height"] == pytest.approx(0.2)
    assert [s["colour"] for s in reply["filaments"]] == ["#FFFFFF", "#101010"] and reply["status"] is None


def test_state_says_when_the_slicing_step_is_missing(loaded):
    config = config_for(BAMBU)
    config.pop("slicing_pipeline_plugin", None)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    assert page_call(loaded, {"cmd": "state"})["selected"] is False


def test_state_carries_the_last_slice(loaded, tmp_path):
    config = config_for(BAMBU)
    save_job(loaded, config)
    target = tmp_path / "plate.gcode"
    target.write_bytes(BAMBU.read_bytes())
    loaded.run_slicing(SLICING, gcode_path=str(target), config_value=config.get)
    assert page_call(loaded, {"cmd": "state"})["status"]["changed"] is True


def test_preview_says_if_the_slicing_step_is_selected(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "preview", "params": params(), "image": gradient()})
    assert isinstance(reply["selected"], bool)


def test_saved_job_from_1_0_1_still_builds():
    from core import pipeline  # noqa: E402
    old = {"version": 1, "params": {"mode": "spiral", "diameter": 42.4, "nozzle": 0.4, "layer_height": 0.2, "base_filament": 2, "art_filament": 3, "art_layers": 1, "flow": 1.0}, "image": None}
    params, image = pipeline.job_from_dict(old)
    assert params.two_filaments and image is None


def test_page_has_bridge(loaded):
    assert "orca.postMessage" in loaded.capability(PAGE).get_ui()


def test_save_writes_job_and_disc(loaded):
    reply = save_job(loaded, config_for(BAMBU))
    assert reply["type"] == "saved"
    assert Path(reply["stl"]).stat().st_size == 84 + 50 * 180 * 4
    assert reply["height"] == pytest.approx(1.0)


def two_filament_config():
    return {**config_for(BAMBU), "filament_colour": "#FFFFFF;#101010"}


def test_two_filaments_write_a_two_part_3mf(loaded):
    harness.set_host(app_info=lambda: {"version": "2.5.0"})
    reply = save_job(loaded, two_filament_config(), base_filament=1, art_filament=2, art_layers=2, layer_height=0.2)
    assert reply["plate"] == "added" and reply["stl"].endswith(".3mf") and reply["height"] == pytest.approx(1.2)
    with zipfile.ZipFile(reply["stl"]) as archive:
        names = archive.namelist()
        settings = archive.read("Metadata/model_settings.config").decode()
        root = archive.read("3D/3dmodel.model").decode()
        meshes = archive.read("3D/Objects/flow_line_art_disc.model").decode()
    assert "Metadata/project_settings.config" not in names  # keeps the user's presets
    assert re.findall(r'<part id="(\d)".*?key="extruder" value="(\d)"', settings) == [("1", "1"), ("2", "2")]
    assert '<metadata name="OrcaSlicer">2.5.0</metadata>' in root
    bottom, top = meshes.split('<object id="2"')
    assert max(float(z) for z in re.findall(r' z="([\d.]+)"', bottom)) == pytest.approx(0.8)
    assert sorted({round(float(z), 3) for z in re.findall(r' z="([\d.]+)"', top)}) == [0.8, 1.2]


def test_one_filament_keeps_the_stl(loaded):
    reply = save_job(loaded, two_filament_config(), base_filament=2, art_filament=2)
    assert reply["stl"].endswith(".stl")


def test_changing_filament_marks_base_stale(loaded):
    harness.set_host(app_info=lambda: {"version": "2.5.0"})
    config = two_filament_config()
    save_job(loaded, config, base_filament=1, art_filament=2)
    assert save_job(loaded, config, on_plate=True, base_filament=2, art_filament=1)["plate"] == "stale"


def test_unknown_filament_slot_is_refused(loaded):
    assert save_job(loaded, config_for(BAMBU) | {"filament_colour": "#FFFFFF"}, art_filament=3)["type"] == "error"


def test_page_lists_filaments(loaded):
    config = two_filament_config()
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    with harness._callback():
        loaded.capability(PAGE).on_message({"cmd": "init"})
    slots = next(m for m in harness.posted if m["type"] == "init")["filaments"]
    assert [s["slot"] for s in slots] == [1, 2] and slots[1]["colour"] == "#101010"


def test_layer_inputs_set_the_base_height(loaded):
    reply = save_job(loaded, config_for(BAMBU), art_layers=2, base_layers=4, layer_height=0.2)
    assert reply["height"] == pytest.approx(1.2)


def test_preview_reports_stack_and_printer(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "preview", "params": params(art_layers=2, layer_height=0.2), "image": gradient()})
    assert reply["stack"]["art"] == pytest.approx(0.4) and reply["printer"]["nozzle"] == pytest.approx(0.4)


def test_init_offers_printer_values(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    with harness._callback():
        loaded.capability(PAGE).on_message({"cmd": "init"})
    sent = next(m for m in harness.posted if m["type"] == "init")["params"]
    assert sent["nozzle"] == pytest.approx(0.4) and sent["layer_height"] == pytest.approx(0.2)
    assert sent["flow"] == 1.0 and sent["art_layers"] == 1


def test_hilbert_job_writes_a_square_base(loaded):
    reply = save_job(loaded, config_for(BAMBU), mode="hilbert")
    assert Path(reply["stl"]).stat().st_size == 84 + 16 * 50


def test_changing_shape_marks_base_stale(loaded):
    config = config_for(BAMBU)
    save_job(loaded, config)
    assert save_job(loaded, config, on_plate=True, mode="hilbert")["plate"] == "stale"


def test_hilbert_preview_reports_pitch(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "preview", "params": params(mode="hilbert"), "image": gradient()})
    assert reply["hilbert"]["pitch"] >= 0.65 and 42.4 in reply["hilbert"]["sizes"]


def test_preview_is_returned(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "preview", "params": params(), "image": gradient()})
    assert reply["type"] == "preview"
    assert len(base64.b64decode(reply["data"])) == reply["size"] ** 2


def test_page_reports_bad_settings(loaded):
    config = config_for(BAMBU)
    harness.set_host(preset_bundle=lambda: harness.fake("orca.host.PresetBundle", full_config_value=config.get))
    reply = page_call(loaded, {"cmd": "preview", "params": params(width_min=0.9), "image": gradient()})
    assert reply["type"] == "error"


@pytest.mark.parametrize("fixture", [BAMBU, KLIPPER])
def test_slicing_replaces_top_layer(loaded, tmp_path, fixture):
    config = config_for(fixture)
    save_job(loaded, config)
    target = tmp_path / "plate.gcode"
    target.write_bytes(fixture.read_bytes())
    result = loaded.run_slicing(SLICING, gcode_path=str(target), config_value=config.get)
    assert result.status == orca.PluginResult.Success
    text = target.read_text(encoding="utf-8")
    assert "; FLOW_LINE_ART_START" in text
    # Start and end G-code survive.
    assert "; EXECUTABLE_BLOCK_START" in text and "; EXECUTABLE_BLOCK_END" in text
    first = target.read_bytes()
    loaded.run_slicing(SLICING, gcode_path=str(target), config_value=config.get)
    assert target.read_bytes() == first  # a second pass changes nothing


def test_slicing_ignores_other_steps(loaded, tmp_path):
    target = tmp_path / "plate.gcode"
    target.write_text("x")
    result = loaded.run_slicing(SLICING, step=orca.slicing.Step.posSlice, gcode_path=str(target))
    assert result.status == orca.PluginResult.Success
    assert target.read_text() == "x"


def test_slicing_leaves_other_prints_alone(loaded, tmp_path):
    config = config_for(BAMBU)
    save_job(loaded, config, diameter=80.0)
    target = tmp_path / "plate.gcode"
    target.write_bytes(BAMBU.read_bytes())
    result = loaded.run_slicing(SLICING, gcode_path=str(target), config_value=config.get)
    assert result.status == orca.PluginResult.Success
    assert target.read_bytes() == BAMBU.read_bytes()
    assert "Not the Flow Line Art disc" in result.message


def test_slicing_without_job_does_nothing(loaded, tmp_path):
    target = tmp_path / "plate.gcode"
    target.write_bytes(BAMBU.read_bytes())
    result = loaded.run_slicing(SLICING, gcode_path=str(target), config_value=lambda k: None)
    assert result.status == orca.PluginResult.Success
    assert target.read_bytes() == BAMBU.read_bytes()


def test_status_reaches_page(loaded, tmp_path):
    config = config_for(BAMBU)
    save_job(loaded, config)
    target = tmp_path / "plate.gcode"
    target.write_bytes(BAMBU.read_bytes())
    loaded.run_slicing(SLICING, gcode_path=str(target), config_value=config.get)
    reply = page_call(loaded, {"cmd": "status"})
    assert reply["status"]["ok"] and reply["status"]["changed"]
