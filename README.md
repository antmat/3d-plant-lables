# Parametric Plant Sign

Parametric generator and ready-to-print files for a two-color plant sign.

Default model:

- Plate: 180 x 90 x 4 mm.
- Rear blind holder for 8 mm composite rebar.
- Holder channel: 8.6 mm.
- Text: `яблоня`, exported as a separate aligned STL for AMS / dual-nozzle printing.
- Print orientation: face down, so printing starts from the flat sign face and text.

User-facing files are in `outputs/`:

- `plate_base.stl`
- `plate_text.stl`
- `plant_sign_generator.py`
- `README.md`

Run tests:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Generate another label:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 outputs/plant_sign_generator.py --text "груша" --outdir outputs
```

