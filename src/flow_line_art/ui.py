"""The page shown in the Flow Line Art tab."""
from .oneline_ui import CSS

_PAGE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
/*ONELINE_CSS*/
.app { height: 100vh; display: grid; gap: var(--ol-pad); padding: var(--ol-pad);
  grid-template-columns: 372px minmax(0, 1fr) 300px; grid-template-rows: minmax(0, 1fr) auto;
  grid-template-areas: "controls stage status" "controls stage actions"; }
.controls { grid-area: controls; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; min-height: 0; }
.stagewrap { grid-area: stage; display: flex; flex-direction: column; gap: 12px; min-height: 0; min-width: 0; }
.status { grid-area: status; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; min-height: 0; }
.actions { grid-area: actions; display: grid; gap: var(--ol-gap); }
.stage { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: var(--ol-pad); flex: 1; min-height: 0; }
.source { overflow-y: auto; }
#crop { width: 100%; aspect-ratio: 1; display: block; border-radius: var(--ol-radius); background: var(--ol-surface-2); cursor: move; touch-action: none; }
.result { padding: 12px; display: flex; flex-direction: column; min-height: 0; min-width: 0; }
.result .ol-preview { flex: 1; padding: 12px; }
#c { max-width: 100%; max-height: 100%; aspect-ratio: 1; display: block; }
#file { position: absolute; width: 1px; height: 1px; opacity: 0; }
#fileName { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#path { word-break: break-all; }
@media (max-width: 1240px) {
  .app { grid-template-columns: 340px minmax(0, 1fr); grid-template-rows: minmax(0, 1fr) auto auto;
    grid-template-areas: "controls stage" "controls status" "controls actions"; }
  .status { flex-direction: row; max-height: 190px; }
  .status > * { flex: 1; min-width: 0; overflow-y: auto; }
  .stage { grid-template-columns: 220px minmax(0, 1fr); }
}
@media (max-width: 760px) {
  .app { display: block; height: auto; min-height: 100%; }
  .controls, .status, .stagewrap { overflow: visible; margin-bottom: 12px; }
  .stage { grid-template-columns: minmax(0, 1fr); }
  .status { flex-direction: column; max-height: none; }
  #c { width: 100%; }
  .actions { position: sticky; bottom: 0; background: var(--orca-bg); padding: 8px 0; }
}
</style>
</head>
<body>
<form class="app" id="f" onsubmit="return false">
  <div class="controls">
    <h1>Flow Line Art</h1>
    <div class="ol-card">
      <h2>Style</h2>
      <div class="ol-segments" id="modes">
        <button type="button" data-mode="spiral">Spiral</button>
        <button type="button" data-mode="raster">Zigzag</button>
        <button type="button" data-mode="hilbert">Hilbert</button>
        <button type="button" data-mode="calibration">Calibrate</button>
      </div>
      <select id="mode" hidden><option value="spiral"></option><option value="raster"></option><option value="hilbert"></option><option value="calibration"></option></select>
    </div>
    <div class="ol-card">
      <h2>Filaments</h2>
      <label class="ol-field">Base <span class="ol-input ol-select"><i id="baseSwatch"></i><select id="base_filament"></select></span></label>
      <label class="ol-field">Line <span class="ol-input ol-select"><i id="artSwatch"></i><select id="art_filament"></select></span></label>
      <label class="ol-field" id="pauseRow">Colour change <span class="ol-input ol-select" style="width:150px"><select id="color_change" style="padding-left:8px"><option value="pause">Pause first</option><option value="none">None</option></select></span></label>
    </div>
    <div class="ol-card">
      <h2>Size and layers</h2>
      <label class="ol-field">Art size <span class="ol-input unit"><input id="diameter" type="number" step="0.1" min="10"><small>mm</small></span></label>
      <label class="ol-field">Ring width <span class="ol-input unit"><input id="ring" type="number" step="0.5" min="0"><small>mm</small></span></label>
      <label class="ol-field">Layer height <span class="ol-input unit"><input id="layer_height" type="number" step="0.01" min="0.04"><small>mm</small></span></label>
      <label class="ol-field">Nozzle <span class="ol-input unit"><input id="nozzle" type="number" step="0.05" min="0.1" max="1.2"><small>mm</small></span></label>
      <label class="ol-field">Base layers <span class="ol-input"><input id="base_layers" type="number" step="1" min="1"></span></label>
      <label class="ol-field">Line layers <span class="ol-input"><input id="art_layers" type="number" step="1" min="1" max="10"></span></label>
      <div class="ol-stack" id="stackBar" hidden><i id="stackBase"></i><i id="stackArt"></i></div>
      <div class="ol-muted" id="stack"></div>
    </div>
    <details class="ol-card">
      <summary>Line width, flow and speed</summary>
      <label class="ol-field">Line pitch <span class="ol-input unit"><input id="pitch" type="number" step="0.01" min="0.1"><small>mm</small></span></label>
      <label class="ol-field">Minimum width <span class="ol-input unit"><input id="width_min" type="number" step="0.01"><small>mm</small></span></label>
      <label class="ol-field">Maximum width <span class="ol-input unit"><input id="width_max" type="number" step="0.01"><small>mm</small></span></label>
      <label class="ol-field">Flow multiplier <span class="ol-input"><input id="flow" type="number" step="0.01" min="0.5" max="1.5"></span></label>
      <label class="ol-field">Print speed <span class="ol-input unit"><input id="speed" type="number" step="1" min="1"><small>mm/s</small></span></label>
      <label class="ol-field">Width change limit <span class="ol-input"><input id="slew" type="number" step="0.01" min="0.01"></span></label>
    </details>
    <details class="ol-card">
      <summary>Tone: invert, contrast, gamma</summary>
      <label class="ol-field">Invert <input id="invert" type="checkbox"></label>
      <label class="ol-field">Contrast <span class="ol-input"><input id="contrast" type="number" step="0.1" min="0.1"></span></label>
      <label class="ol-field">Gamma <span class="ol-input"><input id="gamma" type="number" step="0.05" min="0.1"></span></label>
    </details>
    <div class="ol-card" id="calib" hidden>
      <h2>Calibration</h2>
      <label class="ol-field">Number of steps <span class="ol-input"><input id="steps" type="number" step="1" min="2"></span></label>
      <label class="ol-field">Step that looks mid-gray <span class="ol-input"><input id="midstep" type="number" step="1" min="2"></span></label>
      <button type="button" class="ol-button quiet" id="useStep">Set gamma from it</button>
    </div>
  </div>

  <div class="stagewrap">
    <div class="stage">
      <div class="ol-card source">
        <h2>Picture</h2>
        <canvas id="crop" width="540" height="540" title="Drag to move, scroll to zoom"></canvas>
        <div class="ol-muted" style="margin:8px 0 12px">Drag to move, scroll to zoom</div>
        <div class="ol-muted" id="fileName" style="margin-bottom:8px">No picture yet</div>
        <label class="ol-field">Zoom <span class="ol-input unit"><input id="zoom" type="number" step="0.1" min="1" max="8" value="1"><small>x</small></span></label>
        <label class="ol-field">Left / right <span class="ol-input unit"><input id="panx" type="number" step="5" min="-100" max="100" value="0"><small>%</small></span></label>
        <label class="ol-field">Up / down <span class="ol-input unit"><input id="pany" type="number" step="5" min="-100" max="100" value="0"><small>%</small></span></label>
        <label class="ol-button quiet" style="margin-top:12px;cursor:pointer" id="fileLabel">Choose a picture<input id="file" type="file" accept="image/*"></label>
      </div>
      <div class="ol-card result">
        <h2>The printed line</h2>
        <div class="ol-preview" id="previewBox"><canvas id="c" width="360" height="360"></canvas></div>
      </div>
    </div>
    <div class="ol-metrics">
      <div class="ol-metric"><span class="ol-muted">Line length</span><b id="mLength">-</b></div>
      <div class="ol-metric"><span class="ol-muted">Line time</span><b id="mTime">-</b></div>
      <div class="ol-metric"><span class="ol-muted">Line width</span><b id="mWidth">-</b></div>
      <div class="ol-metric"><span class="ol-muted">Peak flow</span><b id="mFlow">-</b></div>
    </div>
    <div class="ol-muted" id="hilbertNote"></div>
  </div>

  <div class="status">
    <div class="ol-card">
      <h2>Before you slice</h2>
      <div id="checks"></div>
    </div>
    <div class="ol-card">
      <h2>Last slice</h2>
      <div class="ol-muted" id="lastSlice"></div>
    </div>
  </div>

  <div class="actions">
    <div class="ol-muted" id="msg"></div>
    <div class="ol-muted" id="path"></div>
    <button type="button" class="ol-button" id="save">Save job and add base to plate</button>
    <button type="button" class="ol-button quiet" id="refresh">Check last slice</button>
  </div>
</form>
<script>
var fields = ["mode","base_filament","art_filament","color_change","diameter","nozzle","layer_height","base_layers","art_layers","flow","ring","pitch","width_min","width_max","speed","slew","invert","contrast","gamma","steps"];
var image = null, timer = null, ready = false, snapSize = false;
var source = null, encodeTimer = null, filaments = [], filamentKey = "";
var printer = null, selected = null;
// Slicing alone only runs the plugin on Bambu Lab printers; others run it at export or upload.
var NO_RESULT_TEXT = "No result yet. Bambu Lab printers: slice the base. Other printers: export the G-code. Then check here.";
var send = function (m) { window.orca.postMessage(m); };
var el = function (i) { return document.getElementById(i); };

function msg(t, err) { var m = el("msg"); m.textContent = t || ""; m.className = err ? "ol-error" : "ol-muted"; }

function params() {
  var p = {};
  fields.forEach(function (f) {
    var e = el(f);
    p[f] = e.type === "checkbox" ? e.checked : (e.tagName === "SELECT" ? e.value : parseFloat(e.value));
  });
  p.margin = 0.4; p.chord = 0.5;
  return p;
}

function filamentAt(id) { return filaments[parseInt(el(id).value, 10) - 1]; }

function fillFilaments(list) {
  var key = JSON.stringify(list);
  if (key === filamentKey) return;
  filamentKey = key;
  ["base_filament", "art_filament"].forEach(function (id) {
    var e = el(id), keep = e.value;
    e.innerHTML = "";
    list.forEach(function (f) {
      var o = document.createElement("option");
      o.value = f.slot; o.textContent = f.slot + ": " + f.name;
      e.appendChild(o);
    });
    if (keep && parseInt(keep, 10) <= list.length) e.value = keep;
  });
  filaments = list;
  showFilaments();
}

function showFilaments() {
  el("pauseRow").hidden = el("base_filament").value !== el("art_filament").value;
  el("pauseRow").style.display = el("pauseRow").hidden ? "none" : "";
  var base = filamentAt("base_filament"), art = filamentAt("art_filament");
  if (base) { el("baseSwatch").style.background = base.colour; el("stackBase").style.background = base.colour; }
  if (art) { el("artSwatch").style.background = art.colour; el("stackArt").style.background = art.colour; }
}

function luminance(hex) {
  var n = parseInt(hex.slice(1), 16);
  return 0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255);
}

function setParams(p) {
  fields.forEach(function (f) {
    var e = el(f);
    if (e.type === "checkbox") e.checked = !!p[f]; else e.value = p[f];
  });
  el("midstep").value = Math.round(p.steps / 2);
}

function showMode() {
  var mode = el("mode").value;
  Array.prototype.forEach.call(el("modes").children, function (b) { b.className = b.dataset.mode === mode ? "on" : ""; });
  el("calib").hidden = mode !== "calibration";
}

function check(done, title, detail) {
  var row = document.createElement("div"), mark = document.createElement("i"), body = document.createElement("div");
  row.className = done ? "ol-check" : "ol-check todo";
  mark.textContent = done ? "✓" : "!";
  body.textContent = title;
  if (detail) {
    var note = document.createElement("div");
    note.className = "ol-muted"; note.textContent = detail;
    body.appendChild(note);
  }
  row.appendChild(mark); row.appendChild(body);
  el("checks").appendChild(row);
}

function renderChecks() {
  el("checks").innerHTML = "";
  if (el("mode").value !== "calibration") check(!!image, image ? "Picture loaded" : "Pick a picture");
  if (printer) {
    var layer = parseFloat(el("layer_height").value), nozzle = parseFloat(el("nozzle").value);
    var layerOk = Math.abs(layer - printer.layer_height) <= 0.005, nozzleOk = Math.abs(nozzle - printer.nozzle) <= 0.001;
    check(layerOk, layerOk ? "Layer height matches the process preset" : "Layer height differs from the process preset",
      layerOk ? "" : "The preset uses " + printer.layer_height + " mm and the job " + layer + " mm. Match them, or the slice stops with an error.");
    check(nozzleOk, nozzleOk ? "Nozzle matches the printer preset" : "Nozzle differs from the printer preset",
      nozzleOk ? "" : "The preset has a " + printer.nozzle + " mm nozzle and the job " + nozzle + " mm. Match them, or the slice stops with an error.");
  }
  if (selected !== null) {
    check(selected, selected ? "Slicing step is selected" : "Select the slicing step",
      selected ? "" : "Process preset, Others, Slicing Pipeline Plugin: add Flow Line Art G-code.");
  }
  var base = filamentAt("base_filament"), art = filamentAt("art_filament");
  if (base && art && el("base_filament").value !== el("art_filament").value) {
    var dark = luminance(art.colour) < luminance(base.colour), invert = el("invert").checked, good = dark !== invert;
    check(good, good ? "Tone suits the filament colours" : (invert ? "Turn Invert off" : "Turn Invert on"),
      good ? "" : (invert ? "The line filament is darker than the base." : "The line filament is lighter than the base, so the picture would be a negative."));
  }
}

function renderStatus(status) {
  var e = el("lastSlice");
  if (!status) { e.textContent = NO_RESULT_TEXT; e.className = "ol-muted"; return; }
  e.textContent = status.message;
  e.className = status.ok ? "ol-muted" : "ol-error";
}

function renderStack(stack) {
  el("stack").textContent = "Base " + stack.base.toFixed(2) + " mm + line " + stack.art.toFixed(2) + " mm = " + stack.total.toFixed(2) + " mm";
  el("stackBar").hidden = false;
  el("stackBase").style.width = (stack.base / stack.total * 100) + "%";
  el("stackArt").style.width = (stack.art / stack.total * 100) + "%";
}

function renderMetrics(s) {
  el("mLength").textContent = (s.length_mm / 1000).toFixed(1) + " m";
  el("mTime").textContent = Math.round(s.time_s / 60) + " min";
  el("mWidth").textContent = s.width_min.toFixed(2) + " to " + s.width_max.toFixed(2) + " mm";
  el("mFlow").textContent = s.max_flow.toFixed(1) + " mm³/s";
}

function request() {
  if (!ready) return;
  clearTimeout(timer);
  timer = setTimeout(function () {
    if (el("mode").value !== "calibration" && !image) { msg("Pick an image to see the preview."); return; }
    msg("Computing...");
    send({ cmd: "preview", params: params(), image: image });
  }, 350);
}

function bytes(b64) {
  var s = atob(b64), a = new Uint8Array(s.length);
  for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);
  return a;
}

function drawPreview(size, data) {
  var c = el("c"), g = c.getContext("2d"), a = bytes(data);
  c.width = size; c.height = size;
  var img = g.createImageData(size, size);
  for (var i = 0; i < a.length; i++) {
    var v = a[i] / 255, j = i * 4, d = 245 - 215 * v;
    img.data[j] = d; img.data[j + 1] = d; img.data[j + 2] = d; img.data[j + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  fitPreview();
}

function fitPreview() {
  var box = el("previewBox"), side = Math.min(box.clientWidth, box.clientHeight) - 24;
  if (side > 0) { el("c").style.width = side + "px"; el("c").style.height = side + "px"; }
}
window.addEventListener("resize", fitPreview);

function applyState(m) {
  if (m.filaments) fillFilaments(m.filaments);
  if (m.printer) printer = m.printer;
  if (typeof m.selected === "boolean") selected = m.selected;
  renderChecks();
}

window.orca.onMessage(function (m) {
  if (m.type === "init") {
    fillFilaments(m.filaments); setParams(m.params); showFilaments(); ready = true; showMode(); msg("");
    applyState({ printer: { nozzle: m.machine.nozzle, layer_height: m.machine.layer_height }, selected: m.selected });
    request();
  } else if (m.type === "state") {
    applyState(m);
    renderStatus(m.status);
  } else if (m.type === "preview") {
    if (snapSize && m.hilbert) {
      snapSize = false;
      var now = parseFloat(el("diameter").value);
      var best = m.hilbert.sizes.reduce(function (a, b) { return Math.abs(b - now) < Math.abs(a - now) ? b : a; });
      if (Math.abs(best - now) > 0.05) { el("diameter").value = best; request(); return; }
    }
    drawPreview(m.size, m.data); msg("");
    renderStack(m.stack);
    renderMetrics(m.stats);
    applyState(m);
    el("hilbertNote").textContent = m.hilbert ?
      "Line pitch here: " + m.hilbert.pitch.toFixed(2) + " mm. Sizes that keep your pitch: " + m.hilbert.sizes.join(", ") + " mm" : "";
  } else if (m.type === "saved") {
    var notes = {
      added: "Saved. The base is being added to the plate; slice it when it appears.",
      present: "Saved. The base is already on the plate; slice it.",
      stale: "Saved, but the base on the plate has the old size or shape. Delete it from the plate and press the button again.",
      manual: "Saved. The base could not be added automatically; drop this file on the plate:"
    };
    msg(notes[m.plate], m.plate === "stale");
    el("path").textContent = m.plate === "manual" ? m.stl : "";
  } else if (m.type === "gamma") {
    el("gamma").value = m.value; request();
  } else if (m.type === "status") {
    renderStatus(m.status);
  } else if (m.type === "error") {
    msg(m.message, true);
  }
});

function num(id, low, high, fallback) {
  var v = parseFloat(el(id).value);
  return isNaN(v) ? fallback : Math.min(high, Math.max(low, v));
}

function cropBox() {
  var whole = Math.min(source.width, source.height), side = whole / num("zoom", 1, 8, 1);
  var freeX = (source.width - side) / 2, freeY = (source.height - side) / 2;
  return { side: side, freeX: freeX, freeY: freeY,
    x: freeX + freeX * num("panx", -100, 100, 0) / 100, y: freeY + freeY * num("pany", -100, 100, 0) / 100 };
}

function drawCrop() {
  if (!source) return;
  var c = el("crop"), g = c.getContext("2d"), b = cropBox(), n = c.width;
  g.drawImage(source, b.x, b.y, b.side, b.side, 0, 0, n, n);
  if (el("mode").value !== "hilbert" && el("mode").value !== "calibration") {
    g.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--orca-accent") || "#009688";
    g.lineWidth = 4; g.beginPath(); g.arc(n / 2, n / 2, n / 2 - 2, 0, 7); g.stroke();
  }
}

function encode() {
  clearTimeout(encodeTimer); encodeTimer = null;
  if (!source) return;
  var b = cropBox(), target = Math.min(Math.round(b.side), 600);
  var c = document.createElement("canvas"); c.width = target; c.height = target;
  var g = c.getContext("2d");
  g.drawImage(source, b.x, b.y, b.side, b.side, 0, 0, target, target);
  var d = g.getImageData(0, 0, target, target).data, out = new Uint8Array(target * target);
  for (var i = 0; i < out.length; i++) out[i] = Math.round(0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]);
  var s = ""; for (var k = 0; k < out.length; k += 8192) s += String.fromCharCode.apply(null, out.subarray(k, k + 8192));
  image = { width: target, height: target, data: btoa(s) };
  renderChecks();
  request();
}

function moved() {
  drawCrop();
  clearTimeout(encodeTimer);
  encodeTimer = setTimeout(encode, 200);
}

["zoom", "panx", "pany"].forEach(function (id) { el(id).addEventListener("input", moved); });

var drag = null;
el("crop").addEventListener("pointerdown", function (ev) {
  if (!source) return;
  drag = { x: ev.clientX, y: ev.clientY, panx: num("panx", -100, 100, 0), pany: num("pany", -100, 100, 0) };
  el("crop").setPointerCapture(ev.pointerId);
});
el("crop").addEventListener("pointermove", function (ev) {
  if (!drag) return;
  var b = cropBox(), scale = b.side / el("crop").clientWidth;
  if (b.freeX > 0) el("panx").value = Math.round(Math.min(100, Math.max(-100, drag.panx - (ev.clientX - drag.x) * scale / b.freeX * 100)));
  if (b.freeY > 0) el("pany").value = Math.round(Math.min(100, Math.max(-100, drag.pany - (ev.clientY - drag.y) * scale / b.freeY * 100)));
  moved();
});
el("crop").addEventListener("pointerup", function () { drag = null; });
el("crop").addEventListener("wheel", function (ev) {
  if (!source) return;
  ev.preventDefault();
  el("zoom").value = (Math.min(8, Math.max(1, num("zoom", 1, 8, 1) * (ev.deltaY < 0 ? 1.1 : 0.9)))).toFixed(2);
  moved();
}, { passive: false });

["base_filament", "art_filament"].forEach(function (id) { el(id).addEventListener("change", showFilaments); });
el("nozzle").addEventListener("change", function () {
  var n = parseFloat(el("nozzle").value);
  if (!(n > 0)) return;
  el("width_min").value = (n * 0.6).toFixed(2);
  el("width_max").value = (n * 1.6).toFixed(2);
  el("pitch").value = (n * 1.625).toFixed(2);
  request();
});

el("file").addEventListener("change", function (ev) {
  var file = ev.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function () {
    var img = new Image();
    img.onload = function () {
      source = img;
      el("fileName").textContent = file.name;
      el("fileLabel").firstChild.textContent = "Choose another picture";
      el("zoom").value = 1; el("panx").value = 0; el("pany").value = 0;
      drawCrop(); encode();
    };
    img.onerror = function () { msg("This image could not be read.", true); };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
});

Array.prototype.forEach.call(el("modes").children, function (b) {
  b.addEventListener("click", function () {
    el("mode").value = b.dataset.mode;
    el("mode").dispatchEvent(new Event("change"));
  });
});
fields.forEach(function (f) { el(f).addEventListener("change", function () { showMode(); renderChecks(); request(); }); });
el("mode").addEventListener("change", function () { snapSize = el("mode").value === "hilbert"; drawCrop(); });
el("save").addEventListener("click", function () { if (encodeTimer !== null) encode(); send({ cmd: "save", params: params(), image: image }); });
el("refresh").addEventListener("click", function () { send({ cmd: "state" }); });
el("useStep").addEventListener("click", function () {
  send({ cmd: "gamma", index: parseInt(el("midstep").value, 10) - 1, steps: parseInt(el("steps").value, 10) });
});

// The presets change on other tabs, so re-read them when this tab comes back and while it is shown.
document.addEventListener("visibilitychange", function () { if (!document.hidden) send({ cmd: "state" }); });
setInterval(function () { if (!document.hidden) send({ cmd: "state" }); }, 4000);
renderStatus(null);
send({ cmd: "init" });
</script>
</body>
</html>
"""

PAGE_HTML = _PAGE.replace("/*ONELINE_CSS*/", CSS)
