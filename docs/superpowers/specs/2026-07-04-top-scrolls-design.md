# Optional Top Scrolls Design

## Goal

Add optional decorative scroll ornaments near the top of the plant sign. The
ornaments should print in the same second color as the text and remain flush
with the front face, matching the existing two-part Bambu Studio workflow.

## User-Facing Behavior

- `--top-scrolls` enables the decoration.
- When disabled, generated STL files stay visually compatible with the current
  default output.
- When enabled, the generator adds two symmetrical plant-like scroll ornaments
  near the top-left and top-right of the sign.
- The scrolls are included in `plate_text.stl`.
- Matching recesses are included in `plate_base.stl`, so the second-color
  filament is embedded the same way as the text.

## CLI Options

- `--top-scrolls`: boolean flag, default off.
- `--scroll-width`: ornament width in mm, default `32`.
- `--scroll-height`: ornament height in mm, default `12`.
- `--scroll-margin-x`: side margin in mm, default `14`.
- `--scroll-margin-top`: top margin in mm, default `8`.

The defaults should keep ornaments away from the usual centered label text.
Users can increase `--text-margin-y` or set smaller scroll dimensions for very
tall multiline labels.

## Geometry

The scrolls are rasterized into the same XY mask system as text. This keeps the
base topology simple:

- The base remains one connected shell because decorative recesses are folded
  into the existing voxel solid.
- The text part remains a separate aligned second-color STL.
- The scroll mask is unioned with the text mask before pocket generation.

The default ornament is a symmetric pair of simple curling strokes built from
thick sampled curves, plus a small leaf-like flourish. It should read as
botanical decoration without requiring external font or SVG assets.

## Testing

Add focused tests that verify:

- `--top-scrolls` increases the second-color mask area.
- Scroll geometry appears near the top corners and stays inside the plate.
- `plate_base` remains manifold and one connected shell.
- Existing default output without `--top-scrolls` still passes current tests.

## Documentation

Update `README.md` and `outputs/README.md` with a short example:

```bash
python3 outputs/plant_sign_generator.py --text "яблоня" --top-scrolls --outdir outputs
```
