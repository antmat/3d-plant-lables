# Dovetail Holder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default integrated rear holder with a separate support-free dovetail holder and a matching rear socket in the plate.

**Architecture:** Keep the current Python mask/voxel STL generator. `plate_base.stl` remains a face-down printable plate with text recesses, but its rear geometry changes from an integrated cylinder to a female dovetail socket. A new `holder.stl` is generated as a separate upright-printable voxel mesh with a male dovetail tenon and blind 12.6 mm rebar channel.

**Tech Stack:** Python 3, `numpy`, `Pillow`, existing binary STL writer, existing custom regression runner in `work/plant_sign_generator/test_generator.py`.

## Global Constraints

- Default plate thickness is `6.0 mm`.
- Default holder style is `dovetail`.
- Default holder top margin is `12.0 mm`.
- Default holder length is `plate_height - holder_top_margin`, `78.0 mm` for the default plate.
- Default dovetail depth is `3.0 mm`.
- Default dovetail head width is `20.0 mm`.
- Default dovetail neck width is `14.0 mm`.
- Default dovetail clearance is `0.35 mm` per side.
- `plate_base.stl` and `plate_text.stl` stay aligned for multi-material import.
- `holder.stl` is a separate print-oriented file, not aligned as an assembly body.
- The old integrated holder is out of scope for this redesign.

---

### Task 1: Tests For Dovetail Defaults And New Mesh Contract

**Files:**
- Modify: `work/plant_sign_generator/test_generator.py`

**Interfaces:**
- Consumes: current `gen.build_meshes(args)` and CLI tests.
- Produces: tests expecting `gen.build_meshes(args) -> tuple[Mesh, Mesh | None, Mesh, dict[str, object]]`.

- [ ] **Step 1: Update existing `build_meshes` unpacking in tests**

In `work/plant_sign_generator/test_generator.py`, change all unpacking from three values to four values. Examples:

```python
base, text, holder, meta = gen.build_meshes(args)
```

When a test does not need `holder`, use `_`:

```python
base, text, _, meta = gen.build_meshes(args)
```

This is intentionally a RED change: current production code still returns three values.

- [ ] **Step 2: Replace integrated holder tests with dovetail tests**

Remove or rewrite these integrated-holder-specific tests:

```python
test_default_holder_fits_12mm_rebar
test_default_holder_uses_filled_transition
test_base_plate_and_holder_are_one_shell
```

Add:

```python
def test_default_plate_uses_dovetail_holder() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, _, holder, meta = gen.build_meshes(args)
    base_min, base_max = bbox(base)
    holder_min, holder_max = bbox(holder)

    assert args.plate_thickness == 6.0
    assert args.holder_style == "dovetail"
    assert abs(float(meta["holder_length"]) - 78.0) < 0.001
    assert abs(float(meta["channel_diameter"]) - 12.6) < 0.001
    assert abs((base_max[2] - base_min[2]) - 6.0) < 0.001
    assert abs((holder_max[2] - holder_min[2]) - 78.0) < 0.5
    assert int(meta["socket_cells"]) > 0
    assert int(meta["holder_cells"]) > 0
    assert holder.triangles
```

Add:

```python
def test_dovetail_base_and_holder_are_manifold() -> None:
    args = gen.parser().parse_args(["--no-text", "--outdir", "outputs", "--orientation", "front-up"])
    base, text, holder, meta = gen.build_meshes(args)

    assert text is None
    assert non_manifold_edges(base) == {}
    assert non_manifold_edges(holder) == {}
    assert connected_component_count(base) == 1
    assert connected_component_count(holder) == 1
    assert int(meta["socket_cells"]) > 0
```

Add:

```python
def test_dovetail_socket_is_open_at_bottom_and_closed_at_top() -> None:
    args = gen.parser().parse_args(["--no-text", "--outdir", "outputs", "--orientation", "front-up"])
    base, _, _, _ = gen.build_meshes(args)
    points = np.array([point for tri in base.triangles for point in tri], dtype=float)
    rear_socket_points = points[
        (np.abs(points[:, 0]) < args.dovetail_neck_width / 2.0 + args.dovetail_clearance + 1.0)
        & (points[:, 2] < args.dovetail_depth + 0.5)
    ]

    assert rear_socket_points[:, 1].min() <= -args.plate_height / 2.0 + 0.5
    assert rear_socket_points[:, 1].max() < args.plate_height / 2.0 - args.holder_top_margin + 1.0
```

Register the new tests in the `tests = [...]` list.

- [ ] **Step 3: Add CLI holder output tests**

Update `test_no_text_cli_skips_and_removes_plate_text_stl`:

```python
assert os.path.exists(os.path.join(tmp, "holder.stl"))
assert "Generated" in result.stdout
assert "holder.stl" in result.stdout
```

Add:

```python
def test_cli_writes_holder_stl() -> None:
    default_python = shutil.which("python3")
    if not default_python:
        raise AssertionError("python3 was not found on PATH")

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = os.path.join(root, "outputs", "plant_sign_generator.py")
    tmp = os.path.join(root, "work", "test-holder-output")
    os.makedirs(tmp, exist_ok=True)

    result = subprocess.run(
        [default_python, script, "--text", "груша", "--outdir", tmp],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert os.path.exists(os.path.join(tmp, "plate_base.stl"))
    assert os.path.exists(os.path.join(tmp, "plate_text.stl"))
    assert os.path.exists(os.path.join(tmp, "holder.stl"))
    assert "holder.stl" in result.stdout
```

Register this test in `main()`.

- [ ] **Step 4: Run RED tests**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Expected: FAIL because `build_meshes` still returns three values, parser defaults still describe the integrated holder, and CLI does not write `holder.stl`.

- [ ] **Step 5: Keep the failing tests uncommitted until implementation is green**

Do not commit the RED tests by themselves. They deliberately break the branch
until Tasks 2 and 3 implement the new contract.

---

### Task 2: Plate Socket Geometry

**Files:**
- Modify: `work/plant_sign_generator/generate_plant_sign.py`

**Interfaces:**
- Consumes: `add_voxel_solid(mesh, solid, x_edges, y_edges, z_edges)`.
- Produces: `dovetail_width_at_depth(...) -> float`, `add_voxel_base(...)` with socket parameters, metadata `socket_cells`.

- [ ] **Step 1: Add dovetail helper**

Add after `axis_edges(...)`:

```python
def dovetail_width_at_depth(z_from_rear: np.ndarray, neck_width: float, head_width: float, depth: float) -> np.ndarray:
    t = np.clip(z_from_rear / max(depth, 1e-6), 0.0, 1.0)
    return neck_width + (head_width - neck_width) * t
```

- [ ] **Step 2: Change `add_voxel_base` signature**

Change `add_voxel_base(...)` to remove integrated-holder parameters and add socket parameters:

```python
def add_voxel_base(
    mesh: Mesh,
    occupied: np.ndarray,
    pocket: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    z_edges: np.ndarray,
    plate_thickness: float,
    text_depth: float,
    socket_y_min: float,
    socket_y_max: float,
    dovetail_depth: float,
    dovetail_head_width: float,
    dovetail_neck_width: float,
    dovetail_clearance: float,
) -> dict[str, int]:
```

- [ ] **Step 3: Cut the rear socket from the plate solid**

Inside `add_voxel_base`, replace the integrated-holder block with:

```python
xx = x_centers[np.newaxis, np.newaxis, :]
yy = y_centers[np.newaxis, :, np.newaxis]
zz = z_centers[:, np.newaxis, np.newaxis]
socket_z = (zz >= 0.0) & (zz < dovetail_depth)
socket_y = (yy >= socket_y_min) & (yy < socket_y_max)
socket_width = dovetail_width_at_depth(
    zz,
    dovetail_neck_width + 2.0 * dovetail_clearance,
    dovetail_head_width + 2.0 * dovetail_clearance,
    dovetail_depth,
)
socket = socket_z & socket_y & (np.abs(xx) <= socket_width / 2.0)

solid = plate & ~socket
add_voxel_solid(mesh, solid, x_edges, y_edges, z_edges)
return {
    "solid_cells": int(solid.sum()),
    "socket_cells": int(socket.sum()),
}
```

- [ ] **Step 4: Update `build_meshes` base grid for a 6 mm plate**

In `build_meshes`, stop creating negative-z holder space for the base. Use:

```python
holder_length = args.holder_length
if holder_length is None:
    holder_length = args.plate_height - args.holder_top_margin
socket_y_min = -args.plate_height / 2.0
socket_y_max = socket_y_min + holder_length
z_min = 0.0
z_max = args.plate_thickness
```

Update `z_edges` specials to include `args.dovetail_depth` and remove old holder-channel z values:

```python
z_edges = axis_edges(
    z_min,
    z_max,
    args.resolution,
    [
        0.0,
        args.dovetail_depth,
        args.plate_thickness - args.text_depth,
        args.plate_thickness,
    ],
)
```

- [ ] **Step 5: Update `add_voxel_base` call and metadata**

Call:

```python
solid_stats = add_voxel_base(
    base,
    occupied,
    pocket_mask,
    x_edges,
    y_edges,
    z_edges,
    args.plate_thickness,
    args.text_depth,
    socket_y_min,
    socket_y_max,
    args.dovetail_depth,
    args.dovetail_head_width,
    args.dovetail_neck_width,
    args.dovetail_clearance,
)
```

Remove transition metadata and set:

```python
"socket_cells": solid_stats["socket_cells"],
"holder_length": holder_length,
```

- [ ] **Step 6: Run tests**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Expected: tests still FAIL because `holder` mesh and CLI writing are not implemented yet, but base-related failures should be reduced.

Do not commit if syntax errors remain.

---

### Task 3: Separate Holder Mesh

**Files:**
- Modify: `work/plant_sign_generator/generate_plant_sign.py`

**Interfaces:**
- Consumes: `add_voxel_solid(...)`, `axis_edges(...)`, `dovetail_width_at_depth(...)`.
- Produces: `build_holder_mesh(args, holder_length: float) -> tuple[Mesh, dict[str, int]]`.

- [ ] **Step 1: Add holder mesh builder**

Add before `build_meshes(...)`:

```python
def build_holder_mesh(args: argparse.Namespace, holder_length: float) -> tuple[Mesh, dict[str, int]]:
    mesh = Mesh("plant_sign_holder")
    outer_radius = args.holder_outer_diameter / 2.0
    inner_radius = args.rod_diameter / 2.0 + args.rod_clearance / 2.0
    attach_y = -outer_radius + args.dovetail_depth
    y_min = attach_y - args.dovetail_depth
    y_max = outer_radius
    x_limit = max(outer_radius, args.dovetail_head_width / 2.0)
    x_edges = axis_edges(-x_limit, x_limit, args.resolution, [-args.dovetail_head_width / 2.0, args.dovetail_head_width / 2.0])
    y_edges = axis_edges(y_min, y_max, args.resolution, [attach_y, y_min, y_max])
    z_edges = axis_edges(0.0, holder_length, args.resolution, [0.0, holder_length - args.holder_cap_thickness, holder_length])
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2.0
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2.0
    z_centers = (z_edges[:-1] + z_edges[1:]) / 2.0
    xx = x_centers[np.newaxis, :]
    yy = y_centers[:, np.newaxis]
    body = (xx * xx + yy * yy <= outer_radius * outer_radius) & (yy >= attach_y)
    tenon_depth = np.clip((attach_y - yy) / max(args.dovetail_depth, 1e-6), 0.0, 1.0)
    tenon_width = args.dovetail_neck_width + (args.dovetail_head_width - args.dovetail_neck_width) * tenon_depth
    tenon = (yy <= attach_y) & (yy >= y_min) & (np.abs(xx) <= tenon_width / 2.0)
    outer_profile = body | tenon
    channel_profile = xx * xx + yy * yy <= inner_radius * inner_radius
    channel_z = z_centers < holder_length - args.holder_cap_thickness
    solid = outer_profile[np.newaxis, :, :] & np.ones((len(z_centers), 1, 1), dtype=bool)
    channel = channel_z[:, np.newaxis, np.newaxis] & channel_profile[np.newaxis, :, :]
    solid &= ~channel
    add_voxel_solid(mesh, solid, x_edges, y_edges, z_edges)
    return mesh, {
        "holder_cells": int(solid.sum()),
        "channel_cells": int(channel.sum()),
    }
```

- [ ] **Step 2: Return holder from `build_meshes`**

Change the signature:

```python
def build_meshes(args: argparse.Namespace) -> tuple[Mesh, Mesh | None, Mesh, dict[str, object]]:
```

After text mesh creation:

```python
holder, holder_stats = build_holder_mesh(args, holder_length)
```

Do not include `holder` in `orient_face_down(...)`; it already has print orientation.

Update metadata:

```python
"holder_triangles": len(holder.triangles),
"holder_cells": holder_stats["holder_cells"],
"channel_cells": holder_stats["channel_cells"],
"channel_diameter": holder_inner * 2.0,
```

Return:

```python
return base, text, holder, meta
```

- [ ] **Step 3: Update parser defaults and options**

In `parser()`:

```python
p.add_argument("--plate-thickness", type=float, default=6.0)
...
p.add_argument("--holder-style", choices=["dovetail"], default="dovetail")
p.add_argument("--holder-length", type=float, default=None)
p.add_argument("--holder-top-margin", type=float, default=12.0)
p.add_argument("--dovetail-depth", type=float, default=3.0)
p.add_argument("--dovetail-head-width", type=float, default=20.0)
p.add_argument("--dovetail-neck-width", type=float, default=14.0)
p.add_argument("--dovetail-clearance", type=float, default=0.35)
```

Keep hidden legacy parser options only when old commands would otherwise break, but do not use them in geometry.

- [ ] **Step 4: Run tests until GREEN**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Expected: all tests PASS after test unpacking and geometry expectations are aligned.

- [ ] **Step 5: Commit code and tests**

Run:

```bash
git add work/plant_sign_generator/generate_plant_sign.py work/plant_sign_generator/test_generator.py
git commit -m "feat: generate separate dovetail holder"
```

---

### Task 4: CLI Writing, Public Script, Docs, And Outputs

**Files:**
- Modify: `work/plant_sign_generator/generate_plant_sign.py`
- Modify: `outputs/plant_sign_generator.py`
- Modify: `README.md`
- Modify: `outputs/README.md`
- Regenerate: `outputs/plate_base.stl`
- Regenerate: `outputs/plate_text.stl`
- Create/regenerate: `outputs/holder.stl`

**Interfaces:**
- Consumes: `build_meshes(args) -> (base, text, holder, meta)`.
- Produces: CLI writes `holder.stl` in dovetail mode.

- [ ] **Step 1: Update CLI writer**

In `main()`:

```python
base, text, holder, meta = build_meshes(args)

base_path = os.path.join(args.outdir, "plate_base.stl")
text_path = os.path.join(args.outdir, "plate_text.stl")
holder_path = os.path.join(args.outdir, "holder.stl")
write_binary_stl(base, base_path)
write_binary_stl(holder, holder_path)
```

Update output printing:

```python
print(f"Generated {base_path}")
...
print(f"Generated {holder_path}")
```

- [ ] **Step 2: Sync public script**

Run:

```bash
cp work/plant_sign_generator/generate_plant_sign.py outputs/plant_sign_generator.py
```

- [ ] **Step 3: Update docs**

In `README.md` and `outputs/README.md`, replace old integrated-holder wording with:

```markdown
- `plate_base.stl` — plate with rear dovetail socket.
- `plate_text.stl` — second-color text/scroll insert aligned with the plate.
- `holder.stl` — separate support-free dovetail holder with blind 12.6 mm channel.
```

In `outputs/README.md`, update import/printing notes:

```markdown
Import `plate_base.stl` and `plate_text.stl` together as a multi-part object.
Print `holder.stl` as a separate part. Slide the holder into the rear dovetail
socket from the bottom; the closed top of the socket is the stop. A small drop
of glue can be used if the fit is loose.
```

Update useful parameters:

```markdown
--plate-thickness 6
--holder-top-margin 12
--dovetail-clearance 0.35
--dovetail-depth 3
```

- [ ] **Step 4: Regenerate example outputs**

Run:

```bash
python3 outputs/plant_sign_generator.py --text яблоня --top-scrolls --outdir outputs
```

Expected output includes:

```text
Generated outputs/plate_base.stl
Generated outputs/plate_text.stl
Generated outputs/holder.stl
holder_length: 78.0
```

- [ ] **Step 5: Verify final outputs**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/verify_stl.py outputs/plate_base.stl outputs/plate_text.stl outputs/holder.stl
```

Expected: tests PASS; verifier prints dimensions for all three STL files and no bad-edge warnings.

- [ ] **Step 6: Commit and push**

Run:

```bash
git add README.md outputs/README.md outputs/plant_sign_generator.py outputs/plate_base.stl outputs/plate_text.stl outputs/holder.stl work/plant_sign_generator/generate_plant_sign.py work/plant_sign_generator/test_generator.py
git commit -m "feat: ship dovetail holder outputs"
git push origin main
```
