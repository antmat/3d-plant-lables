# Parametric Plant Sign

Parametric generator and ready-to-print files for a two-color plant sign.

Default model:

- Plate: 180 x 90 x 6 mm.
- Rear dovetail socket for a separate holder.
- Separate support-free holder for 12 mm composite rebar.
- Holder channel: 12.6 mm.
- Holder outer diameter: 20 mm.
- Text: `яблоня`, exported as a separate aligned STL for AMS / dual-nozzle printing.
- Print orientation: the plate is face down, so printing starts from the flat sign face and text.
- Assembly: slide `holder.stl` into the rear socket from the bottom; the closed top of the socket is the stop.

User-facing files are in `outputs/`:

- `plate_base.stl`
- `plate_text.stl`
- `holder.stl`
- `plant_sign_generator.py`
- `README.md`

Run tests:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Generate another label:

```bash
python3 outputs/plant_sign_generator.py --text "груша" --outdir outputs
```

Generate the default label with second-color top scrolls:

```bash
python3 outputs/plant_sign_generator.py --text "яблоня" --top-scrolls --outdir outputs
```

Generate multiline text from stdin:

```bash
printf 'яблоня\nMalus domestica\n' | python3 outputs/plant_sign_generator.py \
  --line-size 24 \
  --line-size 8 \
  --outdir outputs
```

Generate a blank sign without text or `plate_text.stl`:

```bash
python3 outputs/plant_sign_generator.py --no-text --outdir outputs
```

Per-line options repeat the last value when there are more lines than values:

```bash
--line-size 24
--line-font "/Library/Fonts/YS Text-Heavy.ttf"
```

If your default Python does not have `numpy` and `Pillow`, the script will
re-run itself with the bundled Codex Python runtime when it is available.
