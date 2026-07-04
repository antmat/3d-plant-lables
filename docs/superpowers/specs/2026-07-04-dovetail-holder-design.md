# Dovetail Holder Redesign

## Goal

Replace the integrated rear holder with a separate printable holder joined to
the plate by a dovetail slide. This should reduce support material, make the
holder print cleaner, and keep the two-color plate workflow intact.

## Output Files

Default generation should produce three user-facing STL files:

- `plate_base.stl`: flat plate with text recesses and a rear dovetail socket.
- `plate_text.stl`: second-color text and optional top scroll inserts, aligned
  with `plate_base.stl` for multi-material import.
- `holder.stl`: separate rear holder in its own support-free print orientation,
  with the matching dovetail tenon and a blind channel for 12 mm composite
  rebar.

The dovetail holder replaces the integrated holder in the default workflow.
Keeping the old integrated holder as a legacy mode is out of scope for this
redesign.

## Plate Geometry

- Plate size: `180 x 90 x 6 mm` by default.
- Text recess remains on the front face, with the existing default depth of
  `0.8 mm`.
- The rear face contains a vertical female dovetail socket.
- The socket is centered horizontally.
- The socket is open at the bottom edge of the plate.
- The socket is closed at the top, so the plate itself acts as the stop.
- The socket top should stop about `12 mm` below the top edge by default.
- The socket bottom aligns with the bottom edge of the plate.
- The socket depth should be about `3.0 mm`, leaving about `3.0 mm` of front
  wall in the default 6 mm plate.

## Holder Geometry

- The holder is a separate part.
- Its bottom aligns with the bottom edge of the plate in the assembled position.
- Its top stops about `12 mm` below the top edge of the plate.
- Holder length is therefore `plate_height - holder_top_margin`, default
  `90 - 12 = 78 mm`.
- The holder includes a male dovetail tenon on the side facing the plate.
- The tenon runs the full holder length.
- The tenon head width should span the full holder width, default `20 mm`.
- The tenon neck width should default to `14 mm`.
- The tenon depth should default to `3.0 mm`.
- The socket clearance should default to `0.35 mm` per side.
- The holder keeps the 12 mm rebar channel:
  - nominal rod diameter: `12.0 mm`;
  - default clearance: `0.6 mm`;
  - channel diameter: `12.6 mm`;
  - top of channel is closed/blind.

## Print Orientation

The plate should keep the existing face-down orientation, so text and optional
scroll inserts print first.

The separate holder should be generated in an orientation suitable for printing
without supports. The rebar channel should be vertical in the printed file, with
the open channel end on the build plate and the blind cap at the top.

## Assembly

The holder slides into the plate from the bottom. The closed top of the socket
stops the holder. Small looseness is acceptable, and a drop of glue is an
expected optional assembly aid.

## CLI

Add or update options so the dovetail design is configurable:

- `--plate-thickness`: default `6.0`.
- `--holder-style`: default `dovetail`.
- `--holder-top-margin`: default `12.0`.
- `--dovetail-depth`: default `3.0`.
- `--dovetail-head-width`: default equal to holder outer diameter, `20.0`.
- `--dovetail-neck-width`: default `14.0`.
- `--dovetail-clearance`: default `0.35`.

The generator should write `holder.stl` when `--holder-style dovetail` is used.

## Testing

Add focused tests for:

- default plate thickness is `6.0 mm`;
- default dovetail mode returns a non-empty `holder` mesh;
- `plate_base` has a rear socket and no integrated rear cylinder;
- `holder.stl` has the expected approximate bounding box;
- generated base, text, and holder meshes have manifold edges;
- `--no-text` still skips `plate_text.stl` while still writing `holder.stl`;
- CLI generation writes `plate_base.stl`, `plate_text.stl`, and `holder.stl`.

## Documentation

Update `README.md` and `outputs/README.md` to describe the new three-file import
workflow and assembly direction. Mention that the separate holder is intended to
print without supports and can be glued after sliding into the plate.
