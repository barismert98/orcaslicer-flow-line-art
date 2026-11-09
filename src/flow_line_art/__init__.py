"""Flow Line Art for OrcaSlicer 2.5."""
import base64
import json
import os
import re

import orca

from . import plate
from .core import art as art_module
from .core import pipeline, placeholder, preview
from .core.image import GrayImage
from .ui import PAGE_HTML

JOB_FILE = "job.json"
STATUS_FILE = "last_run.json"
BASE_NAME = "flow_line_art_disc"
PREVIEW_SIZE = 640


def storage_path(name):
    return os.path.join(orca.host.plugin.storage(), name)


def read_json(name):
    try:
        with open(storage_path(name), encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None


def write_json(name, data):
    with open(storage_path(name), "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def preset_value(key):
    try:
        return orca.host.preset_bundle().full_config_value(key)
    except (RuntimeError, KeyError):
        return None


def current_layer_height():
    try:
        return float(preset_value("layer_height"))
    except (TypeError, ValueError):
        return 0.2


def stack_heights(params, layer_height):
    """Thickness of the base, the art and the whole print, given the slicer's first layer."""
    try:
        first = float(preset_value("initial_layer_print_height"))
    except (TypeError, ValueError):
        first = layer_height
    base = first + (params.base_layers - 1) * layer_height
    art = params.art_layers * layer_height
    return {"base": base, "art": art, "total": base + art}


def printer_state():
    return {"nozzle": art_module.machine_from_config(preset_value).nozzle, "layer_height": current_layer_height()}


def slicing_step_selected():
    return "Flow Line Art G-code" in str(preset_value("slicing_pipeline_plugin") or "")


def filament_slots():
    """The project's filaments, in slot order; slot numbers start at 1."""
    try:
        names = list(orca.host.preset_bundle().current_filament_preset_names())
    except (RuntimeError, AttributeError):
        names = []
    colours = re.findall(r"#[0-9A-Fa-f]{6}", str(preset_value("filament_colour") or ""))
    count = max(len(names), len(colours), 1)
    return [
        {
            "slot": index + 1,
            "name": names[index] if index < len(names) else f"Filament {index + 1}",
            "colour": colours[index] if index < len(colours) else "#808080",
        }
        for index in range(count)
    ]


def running_version():
    return str(orca.host.app_info()["version"])


def disc_on_plate():
    try:
        objects = orca.host.model().objects()
    except RuntimeError:
        return False
    return any(BASE_NAME in (obj.input_file or obj.name or "") for obj in objects)


def image_from_message(raw):
    return GrayImage.from_base64(raw["width"], raw["height"], raw["data"]) if raw else None


class FlowLineArtPage(orca.pages.PagesPluginCapabilityBase):
    def get_name(self):
        return "Flow Line Art"

    def get_ui(self):
        return PAGE_HTML

    def get_icon(self):
        """OrcaSlicer strips the extension, adds .svg and uses an existing path as it is."""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.svg").replace("\\", "/")

    def on_message(self, data):
        handlers = {
            "init": self._init,
            "preview": self._preview,
            "save": self._save,
            "gamma": self._gamma,
            "status": self._status,
            "state": self._state,
        }
        handler = handlers.get(data.get("cmd"))
        if handler is None:
            return
        try:
            handler(data)
        except (art_module.ArtError, ValueError, OSError) as error:
            self.post_message({"type": "error", "message": str(error)})

    def _init(self, _data):
        machine = art_module.machine_from_config(preset_value)
        nozzle = machine.nozzle
        defaults = art_module.Params(
            nozzle=nozzle,
            layer_height=current_layer_height(),
            width_min=round(nozzle * 0.6, 2),
            width_max=round(nozzle * 1.6, 2),
            pitch=round(nozzle * 1.625, 2),
        )
        self.post_message({
            "type": "init",
            "params": defaults.to_dict(),
            "machine": {
                "nozzle": nozzle,
                "filament": machine.filament_diameter,
                "layer_height": current_layer_height(),
                "max_flow": machine.max_volumetric,
                "bed": list(machine.bed),
                "pause": bool(machine.pause_gcode),
            },
            "filaments": filament_slots(),
            "selected": slicing_step_selected(),
        })
        self._status(None)

    def _state(self, _data):
        """What the checklist shows: read from the presets each time, never remembered."""
        self.post_message({
            "type": "state",
            "printer": printer_state(),
            "selected": slicing_step_selected(),
            "filaments": filament_slots(),
            "status": read_json(STATUS_FILE),
        })

    def _build(self, data):
        machine = art_module.machine_from_config(preset_value)
        params = art_module.Params.from_dict(data["params"])
        slots = len(filament_slots())
        if max(params.base_filament, params.art_filament) > slots:
            raise art_module.ArtError(f"This project has {slots} filament(s). Add more in the filament list first.")
        image = image_from_message(data.get("image"))
        return params, image, art_module.build(params, image, machine, params.layer_height or current_layer_height())

    def _preview(self, data):
        _params, _image, art = self._build(data)
        coverage = preview.render(art, PREVIEW_SIZE)
        self.post_message({
            "type": "preview",
            "size": PREVIEW_SIZE,
            "data": base64.b64encode(coverage).decode("ascii"),
            "stats": art.stats(),
            "hilbert": art_module.hilbert_info(art.params) if art.params.mode == "hilbert" else None,
            "stack": stack_heights(art.params, art.layer_height),
            "filaments": filament_slots(),
            "printer": printer_state(),
            "selected": slicing_step_selected(),
        })

    def _save(self, data):
        params, image, art = self._build(data)
        stack = stack_heights(params, art.layer_height)
        height = stack["total"]
        disc = {
            "diameter": params.diameter,
            "height": height,
            "square": params.square,
            "filaments": [params.base_filament, params.art_filament],
        }
        previous = read_json(JOB_FILE) or {}
        job = pipeline.job_to_dict(params, image)
        job["disc"] = disc
        write_json(JOB_FILE, job)
        if params.two_filaments:
            bed = art.machine.bed
            content = placeholder.two_filament_3mf(
                params.diameter,
                params.square,
                stack["base"],
                height,
                params.base_filament,
                params.art_filament,
                ((bed[0] + bed[2]) / 2, (bed[1] + bed[3]) / 2),
                running_version(),
            )
            path = storage_path(BASE_NAME + ".3mf")
        else:
            content = placeholder.base_stl(params.diameter, params.square, height)
            path = storage_path(BASE_NAME + ".stl")
        with open(path, "wb") as handle:
            handle.write(content)
        if disc_on_plate():
            state = "present" if previous.get("disc") == disc else "stale"
        else:
            state = "added" if plate.add_to_plate(path) else "manual"
        self.post_message({"type": "saved", "stl": path, "height": height, "plate": state})

    def _gamma(self, data):
        gamma = art_module.gamma_from_step(int(data["index"]), int(data["steps"]))
        self.post_message({"type": "gamma", "value": round(gamma, 3)})

    def _status(self, _data):
        self.post_message({"type": "status", "status": read_json(STATUS_FILE)})


class FlowLineArtSlicing(orca.slicing.SlicingPipelineCapabilityBase):
    def get_name(self):
        return "Flow Line Art G-code"

    def execute(self, ctx):
        if ctx.step != orca.slicing.Step.psGCodePostProcess:
            return orca.ExecutionResult.success("")
        try:
            with open(ctx.gcode_path, encoding="utf-8", newline="") as handle:
                text = handle.read()
            outcome = pipeline.process(text, read_json(JOB_FILE), ctx.config_value)
            if outcome.changed:
                with open(ctx.gcode_path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(outcome.text)
        except (art_module.ArtError, ValueError, OSError) as error:
            write_json(STATUS_FILE, {"ok": False, "message": str(error)})
            return orca.ExecutionResult.failure(orca.PluginResult.RecoverableError, f"Flow Line Art: {error}")
        write_json(STATUS_FILE, {"ok": True, "changed": outcome.changed, "message": outcome.message})
        return orca.ExecutionResult.success(outcome.message)


@orca.plugin
class FlowLineArtPlugin(orca.base):
    def register_capabilities(self):
        orca.register_capability(FlowLineArtPage)
        orca.register_capability(FlowLineArtSlicing)
