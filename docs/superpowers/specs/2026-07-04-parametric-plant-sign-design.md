# Parametric Plant Sign Design

Date: 2026-07-04

## Goal

Create a parametric generator for printable plant labels. The initial label text is
`яблоня`, but the generator must allow arbitrary text values without rebuilding the
model by hand.

## Printer and Workflow

Target printer: Bambu Lab X2D with AMS and two nozzles.

The model should export as separate, aligned bodies so the slicer can assign
different filaments:

- `plate_base.stl`: base plate, rear post holder, and recessed text pocket.
- `plate_text.stl`: colored text insert, aligned to the same coordinate system.

The two files should import into Bambu Studio as a single assembly/object with
separate material assignments.

## Geometry

Base plate:

- Width: 180 mm.
- Height: 90 mm.
- Thickness: 4 mm.
- Slightly rounded corners.
- Front face contains a recessed pocket for the text insert.

Text:

- Default text: `яблоня`.
- Text is a separate body intended for a different color filament.
- Text sits flush with the front face, or up to 0.05 mm proud if needed for slicer
  robustness.
- Text pocket depth: about 0.8 mm.
- Text should be scaled or parameterized to fit within the label while preserving
  margins.
- Font must support Cyrillic.

Rear holder:

- Position: centered horizontally on the rear face.
- Orientation: vertical when the label is installed.
- Shape: external cylinder fused to the rear of the plate.
- Top: closed/blind.
- Bottom: open.
- Internal channel: circular, nominal 12.6 mm diameter for 12 mm composite rebar.
- External holder diameter: about 24 mm.
- Holder length along the label height: about 65 mm.
- Smooth side transitions/fillets should blend the holder into the plate for
  strength and appearance.

## Modeling Approach

Use a Python STL generator as the primary implementation:

- It can run with the bundled Codex Python runtime.
- It avoids requiring OpenSCAD on this machine for the first printable output.
- The script can be invoked from the command line to generate different text.
- Separate output files export the base and text bodies.
- Text geometry is generated from a TrueType/OpenType font rendered into a
  high-resolution mask and extruded into a thin STL insert.

The design favors exact round geometry for the internal holder channel. Supports
inside the blind channel are acceptable; if needed, the channel can be drilled out
after printing.

## Parameters

Expected configurable values:

- `label_text`.
- `plate_width`.
- `plate_height`.
- `plate_thickness`.
- `corner_radius`.
- `text_font`.
- `text_size`.
- `text_depth`.
- `text_margin`.
- `rod_diameter`.
- `rod_clearance`.
- `holder_outer_diameter`.
- `holder_length`.
- `holder_cap_thickness`.

## Verification

Before delivery:

- Generate the default `яблоня` base STL.
- Generate the default `яблоня` text STL.
- Verify files exist and are non-empty.
- If STL tooling is available, inspect bounding boxes for approximate expected
  dimensions.
