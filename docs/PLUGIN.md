# Flow Line Art

Upload any photo and get a disc printed as a single unbroken spiral. The picture appears because the line swells and thins, with no color changes inside the picture.

**How to use**
1. Open the Flow Line Art tab and pick an image. Drag it to position it, scroll to zoom.
2. Choose the art size, the base and art filaments, the layer height and the number of base and art layers.
3. Press Save job and add base to plate. The base lands on the plate, with each filament already assigned.
4. In the process preset, under Others, set Slicing Pipeline Plugin to Flow Line Art G-code.
5. Slice. On a Bambu Lab printer the preview shows the line.

**The Slicing Pipeline Plugin setting**
The picture is made when you slice. Flow Line Art adds a slicing step that finds the top layers of its base and replaces them with the line. OrcaSlicer runs that step only when it is selected: in the process preset, open Others, find Slicing Pipeline Plugin, press Add plugin and choose Flow Line Art G-code. Save the preset to keep it. A print that is not the Flow Line Art base is left as it is, so the setting can stay on.

**What it does**
- Draws the picture as one continuous line, with no travel moves inside the art.
- Changes only the filament flow along the line, at a constant speed, within your filament's volumetric limit.
- Spiral, zigzag lines, or a Hilbert curve on a square base.
- Choose the outer shape: square, circle, rectangle, oval or hexagon. Zigzag fits them all, Spiral and Relief fit a circle, square or rectangle, and Hilbert needs a square.
- Relief: darker parts of the picture print as more stacked passes of the line, so the disc gains depth in raking light. Choose 2 to 6 line layers.
- Automatic tone stretches the picture over its real light-to-dark range. You can turn it off, and contrast, gamma and the line width range have sliders.
- Separate filaments for the base and the art, or one filament with a pause to swap it.
- One or more art layers, which retrace the same line.
- Calibration pattern, to match tones to your filaments.
- Flow multiplier, contrast, gamma and invert.

**Notes**
- Tested with real prints on a Bambu Lab X1 Carbon. Klipper G-code was tested on sliced files only, not printed.
- On printers other than Bambu Lab the slicer preview shows the plain base. The line is in the exported file.
- Adding the base to the plate automatically is Windows only. Elsewhere, the page shows the file to import.
- The layer height and nozzle you enter must match your presets, or the slice stops with a message.
- Free and open source, GPL-3.0-or-later.

Has a picture that did not come out well? Leave a comment with a photo of the print and your settings.
