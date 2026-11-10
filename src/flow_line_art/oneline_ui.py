"""OneLine family look: the reusable style block. Every color derives from OrcaSlicer's theme."""

CSS = r"""
:root {
  --ol-surface: color-mix(in srgb, var(--orca-fg) 5%, var(--orca-bg));
  --ol-surface-2: color-mix(in srgb, var(--orca-fg) 10%, var(--orca-bg));
  --ol-line: color-mix(in srgb, var(--orca-border) 75%, transparent);
  --ol-ok: var(--orca-accent);
  --ol-warn: #d9822b;
  --ol-error: #e5484d;
  --ol-radius: 6px;
  --ol-gap: 8px;
  --ol-pad: 16px;
  --ol-text: 13px;
  --ol-small: 12px;
  --ol-control: 30px;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body { background: var(--orca-bg); color: var(--orca-fg); font: var(--ol-text)/1.4 var(--orca-font); }
h1 { font-size: 16px; font-weight: 600; margin: 0; }
h2 { font-size: var(--ol-small); font-weight: 600; margin: 0 0 var(--ol-gap); color: var(--orca-muted); }
.ol-muted { color: var(--orca-muted); font-size: var(--ol-small); }
.ol-error { color: var(--ol-error); font-size: var(--ol-small); }
.ol-card { background: var(--ol-surface); border: 1px solid var(--ol-line); border-radius: var(--ol-radius); padding: var(--ol-pad); }
.ol-field { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: var(--ol-control); margin-bottom: 6px; }
.ol-field:last-child { margin-bottom: 0; }
.ol-field.ol-slider { display: grid; grid-template-columns: 96px minmax(0, 1fr) 104px; gap: 10px; }
.ol-slider input[type=range] { -webkit-appearance: none; width: 100%; height: var(--ol-control); margin: 0; background: transparent; }
.ol-slider input::-webkit-slider-runnable-track { height: 4px; border-radius: 2px; background: var(--orca-border); }
.ol-slider input::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; margin-top: -5px; border-radius: 50%; background: var(--orca-accent); }
.ol-slider input:focus-visible { outline: 2px solid var(--orca-accent); }
.ol-slider input:disabled { opacity: .5; }
.ol-input { position: relative; flex: none; width: 104px; height: var(--ol-control); }
.ol-input input, .ol-input select { width: 100%; height: 100%; padding: 0 8px; background: var(--orca-bg); color: var(--orca-fg); border: 1px solid var(--orca-border); border-radius: var(--ol-radius); font: inherit; }
.ol-input small { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: var(--orca-muted); font-size: 11px; pointer-events: none; }
.ol-input.unit input { padding-right: 32px; }
.ol-input input::-webkit-inner-spin-button { display: none; }
.ol-select { width: 196px; }
.ol-select select { padding-left: 30px; }
.ol-select i { position: absolute; left: 8px; top: 8px; width: 14px; height: 14px; border-radius: 3px; border: 1px solid var(--orca-border); pointer-events: none; }
.ol-segments { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; border: 1px solid var(--orca-border); border-radius: var(--ol-radius); overflow: hidden; }
.ol-segments button { height: var(--ol-control); border: 0; border-left: 1px solid var(--orca-border); background: transparent; color: var(--orca-fg); font: inherit; cursor: pointer; }
.ol-segments button:first-child { border-left: 0; }
.ol-segments button:disabled { opacity: .4; cursor: not-allowed; }
.ol-segments button.on { background: var(--orca-accent); color: var(--orca-accent-fg); }
.ol-button { min-height: 36px; width: 100%; padding: 0 16px; border: 0; border-radius: var(--ol-radius); background: var(--orca-accent); color: var(--orca-accent-fg); font: 600 var(--ol-text) var(--orca-font); cursor: pointer; }
.ol-button.quiet { display: flex; align-items: center; justify-content: center; background: transparent; color: var(--orca-fg); border: 1px solid var(--orca-border); font-weight: 400; }
details.ol-card > summary { display: flex; justify-content: space-between; align-items: center; min-height: var(--ol-control); cursor: pointer; list-style: none; }
details.ol-card > summary::-webkit-details-marker { display: none; }
details.ol-card > summary::after { content: ""; width: 7px; height: 7px; border-right: 1.5px solid var(--orca-muted); border-bottom: 1.5px solid var(--orca-muted); transform: rotate(-45deg); }
details.ol-card[open] > summary { margin-bottom: 8px; }
details.ol-card[open] > summary::after { transform: rotate(45deg); }
.ol-stack { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 8px 0 4px; background: var(--ol-surface-2); }
.ol-stack i { display: block; height: 100%; }
.ol-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: var(--ol-gap); }
.ol-metric { background: var(--ol-surface); border: 1px solid var(--ol-line); border-radius: var(--ol-radius); padding: 8px 12px; }
.ol-metric b { display: block; font-size: 15px; font-weight: 600; }
.ol-check { display: grid; grid-template-columns: 18px 1fr; gap: 8px; margin-bottom: 12px; }
.ol-check:last-child { margin-bottom: 0; }
.ol-check > i { width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-style: normal; font-weight: 700; font-size: 11px; background: var(--ol-ok); color: var(--orca-accent-fg); }
.ol-check.todo > i { background: var(--ol-warn); color: #fff; }
.ol-preview { background: rgb(245, 245, 245); border-radius: var(--ol-radius); display: flex; align-items: center; justify-content: center; min-height: 0; }
"""
