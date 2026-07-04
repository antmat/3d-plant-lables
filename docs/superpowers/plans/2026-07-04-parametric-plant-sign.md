# Parametric Plant Sign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python generator that creates aligned STL files for a 180 x 90 x 4 mm plant label with a colored inlaid Cyrillic text body and a rear blind holder for 12 mm composite rebar.

**Architecture:** The generator creates simple triangle meshes directly: rounded plate primitives, a raster-derived text insert, a matching text recess in the plate, and rear holder solids. A small verifier reads binary STL headers and bounding boxes so the generated output can be checked without external CAD software.

**Tech Stack:** Python 3, bundled `numpy`, bundled `Pillow`, binary STL output, shell commands.

## Global Constraints

- Target printer: Bambu Lab X2D with AMS and two nozzles.
- Output parts: `plate_base.stl` and `plate_text.stl`, aligned to the same coordinate system.
- Base plate: 180 mm width, 90 mm height, 4 mm thickness.
- Default text: `яблоня`.
- Text pocket depth: about 0.8 mm.
- Rear holder: centered, vertical, external cylinder about 20 mm diameter, about 65 mm long.
- Holder channel: circular, blind at the top, open at the bottom, nominal 12.6 mm diameter for 12 mm composite rebar.
- Current workspace is not a git repository, so verification replaces commit steps.

---

### Task 1: Generator and CLI

**Files:**
- Create: `work/plant_sign_generator/generate_plant_sign.py`
- Create: `outputs/plant_sign_generator.py`

**Interfaces:**
- Consumes: command-line arguments for label text, dimensions, font path, and output directory.
- Produces: `plate_base.stl`, `plate_text.stl`, and a copied user-facing generator script.

- [ ] **Step 1: Write the failing smoke test**

Run this before creating the generator:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/generate_plant_sign.py --text яблоня --outdir outputs
```

Expected: fail because `work/plant_sign_generator/generate_plant_sign.py` does not exist.

- [ ] **Step 2: Create the generator**

Implement `generate_plant_sign.py` with:

- CLI defaults matching the global constraints.
- Binary STL writer.
- Rounded plate mesh.
- Raster text mask using `/Library/Fonts/YS Text-Heavy.ttf`.
- Text insert mesh from the mask.
- Base mesh with a text-shaped recessed pocket from the same mask.
- Rear blind cylindrical holder with a 12.6 mm internal channel.
- Two filled side transitions from holder to plate along the full holder length.

- [ ] **Step 3: Run the smoke test**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/generate_plant_sign.py --text яблоня --outdir outputs
```

Expected: exit 0 and creation of `outputs/plate_base.stl` and `outputs/plate_text.stl`.

- [ ] **Step 4: Copy the generator to outputs**

Run:

```bash
cp work/plant_sign_generator/generate_plant_sign.py outputs/plant_sign_generator.py
```

Expected: `outputs/plant_sign_generator.py` exists.

### Task 2: Verification and Usage Notes

**Files:**
- Create: `work/plant_sign_generator/verify_stl.py`
- Create: `outputs/README.md`

**Interfaces:**
- Consumes: the two STL files from Task 1.
- Produces: bounding-box verification and user instructions.

- [ ] **Step 1: Create the verifier**

Implement `verify_stl.py` to read binary STL files, count triangles, and print bounding boxes.

- [ ] **Step 2: Run verification**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/verify_stl.py outputs/plate_base.stl outputs/plate_text.stl
```

Expected:

- `plate_base.stl` has nonzero triangles.
- `plate_text.stl` has nonzero triangles.
- Base bounding box is approximately 180 mm wide, 90 mm tall, and includes the rear holder behind the plate.
- Text bounding box lies within the plate front area.

- [ ] **Step 3: Create usage notes**

Write `outputs/README.md` with:

- What each STL file is.
- How to import both STL files into Bambu Studio as a multi-part object.
- How to generate a custom text label.
- Which parameters are most useful to tune.

- [ ] **Step 4: Final verification**

Run:

```bash
ls -lh outputs/plate_base.stl outputs/plate_text.stl outputs/plant_sign_generator.py outputs/README.md
```

Expected: all four user-facing output files exist and are non-empty.
