# Changelog

## Unreleased
- 2026-11-08: project created by the factory.
- 2026-11-08: the save button adds the placeholder disc to the plate on Windows.
- 2026-11-08: spiral, raster and calibration modes; Pages tab with preview; top-layer replacement at `psGCodePostProcess`.
- 2026-11-08: Hilbert curve mode on a square base (0.1.2).
- 2026-11-08: Inputs for image position, nozzle, layer height, base and art layers, and a flow multiplier (0.1.3).
- 2026-11-08: Separate filaments for the base and the art, assigned automatically in a two-part 3MF (0.1.4).
- 2026-11-09: 1.0.0: listing texts, screenshots, GPL-3.0-or-later license, package renamed Flow-Line-Art.
- 2026-11-09: 1.0.0 published on Orca Cloud.
- 2026-11-09: 1.0.1: the tab shows a simplified moon-spiral icon, made for 20 px (`src/flow_line_art/icon.svg`). Published on Orca Cloud; the file published as 1.0.0 does not have it.
- 2026-11-09: 1.1.0: Workbench layout for the tab: one screen, fixed Save, folded advanced settings, a checklist read from the presets, separate stats, a sharper preview. Job output is unchanged.
- 2026-11-09: 1.1.0 published on Orca Cloud, review low risk: new one-screen interface, larger line preview, advanced settings folded away, a live checklist before slicing, and the save button always in view.
- 2026-11-09: 1.1.1: the empty Last slice panel says that Bambu Lab printers need a slice and other printers need a G-code export, after a user comment on Orca Cloud.
- 2026-11-09: 1.1.1 published on Orca Cloud, automated review low risk.
- 2026-11-09: 1.2.0: Relief mode. Darker parts of the picture print as more stacked passes of the line, on a spiral disc. The tab shows the height steps in its preview and warns when the prime tower is off with two filaments. Job files now carry the mode (format version 2).
- 2026-11-09: 1.2.1: the two-part base file shares its vertices, so each part is a closed mesh. The stale task about the listing's first screenshot was removed: the live page already shows the workbench.
- 2026-11-09: Added `tools/benchmark.py`, which draws a benchmark sheet per picture mode. Plugin files are unchanged.
- 2026-11-10: 1.3.0: automatic tone for every picture mode, on when the tab starts and saved in the job; jobs saved before it stay off. Sliders for contrast, gamma, minimum width and maximum width, each paired with its number. Starting contrast 1.2, chosen on the benchmark.
- 2026-11-10: 1.4.0: choose the art's outer shape: circle, square, rectangle, oval or hexagon. Zigzag fits all of them, Spiral and Relief a circle, square or rectangle, Hilbert a square; other choices are off with a reason. Jobs saved before keep their old outline.
- 2026-11-10: 1.4.1: rounded rectangle added for Zigzag, off with a reason in the other modes. The shape picker now has the same order as the other image plugins.
- 2026-11-10: 1.4.2: American English in the tab, messages, docs and comments. OrcaSlicer's own keys and saved job data keep their names; the G-code is unchanged.
- 2026-11-10: 1.4.3: the shape table's keys are now `shapes_by_mode` and `unavailable_notes`, and three docstrings are restated as plain description. Two comment typos from 1.4.2 ("centerd") are fixed. The tab's text and the G-code are unchanged.
- 2026-11-10: 1.4.4: the comment on the shape list now describes what the tuple holds. No change to the tab or the G-code.
- 2026-11-10: 1.4.5: rounded rectangle removed, five shapes remain in the same order. A saved job naming it stops with a clear message. The G-code of the remaining shapes is unchanged.
- 2026-11-10: 1.4.5 published on Orca Cloud (low risk, no review flag) and on GitHub as release v1.4.5. Relief printed rough and is marked experimental on the page.
