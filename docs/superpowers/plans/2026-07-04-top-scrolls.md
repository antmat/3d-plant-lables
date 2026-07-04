# Optional Top Scrolls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional second-color decorative plant scrolls near the top of the sign.

**Architecture:** Scrolls are rasterized into a boolean XY mask, unioned with the existing text mask, then reused for both the base recess and `plate_text.stl`. The base stays a single voxel-derived shell because the pocket mask already feeds `add_voxel_base`.

**Tech Stack:** Python 3, `numpy`, `Pillow`, existing binary STL writer, existing custom test runner in `work/plant_sign_generator/test_generator.py`.

## Global Constraints

- `--top-scrolls` is opt-in and defaults off.
- Scrolls print in the same second-color STL as text.
- Base recesses must match the combined text plus scroll mask.
- `plate_base` must remain manifold and one connected shell.
- No external font, SVG, CAD, or geometry dependency is required for the scroll artwork.

---

### Task 1: Scroll Mask And CLI

**Files:**
- Modify: `work/plant_sign_generator/generate_plant_sign.py`
- Modify: `work/plant_sign_generator/test_generator.py`

**Interfaces:**
- Consumes: `rounded_rect_occupancy(...)`, `fill_diagonal_contacts(...)`, `add_voxel_base(...)`, and existing `text_mask` / `pocket_mask` flow.
- Produces: `make_top_scroll_mask(...) -> np.ndarray`, parser options `--top-scrolls`, `--scroll-width`, `--scroll-height`, `--scroll-margin-x`, `--scroll-margin-top`, metadata key `scroll_cells`.

- [ ] **Step 1: Write the failing tests**

Add these tests to `work/plant_sign_generator/test_generator.py`:

```python
def test_top_scrolls_add_second_color_geometry_near_top_corners() -> None:
    args_plain = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs", "--orientation", "front-up"])
    _, text_plain, meta_plain = gen.build_meshes(args_plain)
    args_scrolls = gen.parser().parse_args([
        "--text",
        "яблоня",
        "--top-scrolls",
        "--outdir",
        "outputs",
        "--orientation",
        "front-up",
    ])
    base_scrolls, text_scrolls, meta_scrolls = gen.build_meshes(args_scrolls)
    points = np.array([point for tri in text_scrolls.triangles for point in tri], dtype=float)
    top_left = points[
        (points[:, 0] < -args_scrolls.plate_width / 2.0 + args_scrolls.scroll_margin_x + args_scrolls.scroll_width + 2.0)
        & (points[:, 1] > args_scrolls.plate_height / 2.0 - args_scrolls.scroll_margin_top - args_scrolls.scroll_height - 2.0)
    ]
    top_right = points[
        (points[:, 0] > args_scrolls.plate_width / 2.0 - args_scrolls.scroll_margin_x - args_scrolls.scroll_width - 2.0)
        & (points[:, 1] > args_scrolls.plate_height / 2.0 - args_scrolls.scroll_margin_top - args_scrolls.scroll_height - 2.0)
    ]

    assert int(meta_scrolls["scroll_cells"]) > 0
    assert int(meta_scrolls["text_cells"]) > int(meta_plain["text_cells"])
    assert len(text_scrolls.triangles) > len(text_plain.triangles)
    assert len(top_left) > 0
    assert len(top_right) > 0
    assert non_manifold_edges(base_scrolls) == {}
    assert non_manifold_edges(text_scrolls) == {}
    assert connected_component_count(base_scrolls) == 1
```

Add this test to ensure the default remains off:

```python
def test_top_scrolls_default_off() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    _, _, meta = gen.build_meshes(args)

    assert int(meta["scroll_cells"]) == 0
```

Register both tests in the `tests = [...]` list in `main()`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Expected: FAIL because parser does not know `--top-scrolls` and `scroll_cells` is not present.

- [ ] **Step 3: Add scroll mask helpers**

In `work/plant_sign_generator/generate_plant_sign.py`, add these helpers after `dilate_mask(...)`:

```python
def draw_disk(mask: np.ndarray, x_centers: np.ndarray, y_centers: np.ndarray, cx: float, cy: float, radius: float) -> None:
    xx, yy = np.meshgrid(x_centers, y_centers)
    mask |= (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= radius * radius


def draw_polyline(mask: np.ndarray, x_centers: np.ndarray, y_centers: np.ndarray, points: list[tuple[float, float]], radius: float) -> None:
    samples_per_mm = 2.5
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(math.ceil(length * samples_per_mm)))
        for step in range(steps + 1):
            t = step / steps
            draw_disk(mask, x_centers, y_centers, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, radius)


def scroll_curve_points(cx: float, cy: float, width: float, height: float, mirror: bool) -> list[tuple[float, float]]:
    points = []
    turns = 1.65
    for index in range(90):
        t = index / 89.0
        angle = turns * 2.0 * math.pi * t
        radius = (1.0 - t) * min(width, height) * 0.42
        x = cx + width * (t - 0.5) * 0.72 + radius * math.cos(angle)
        y = cy + radius * math.sin(angle) * 0.75
        if mirror:
            x = 2.0 * cx - x
        points.append((x, y))
    return points


def make_top_scroll_mask(
    x_centers: np.ndarray,
    y_centers: np.ndarray,
    plate_width: float,
    plate_height: float,
    width: float,
    height: float,
    margin_x: float,
    margin_top: float,
) -> np.ndarray:
    mask = np.zeros((len(y_centers), len(x_centers)), dtype=bool)
    stroke = max(0.8, min(width, height) * 0.12)
    center_y = plate_height / 2.0 - margin_top - height / 2.0
    left_center_x = -plate_width / 2.0 + margin_x + width / 2.0
    right_center_x = plate_width / 2.0 - margin_x - width / 2.0
    for center_x, mirror in ((left_center_x, False), (right_center_x, True)):
        curve = scroll_curve_points(center_x, center_y, width, height, mirror)
        draw_polyline(mask, x_centers, y_centers, curve, stroke)
        leaf_x = center_x + (-width * 0.24 if mirror else width * 0.24)
        draw_polyline(
            mask,
            x_centers,
            y_centers,
            [
                (leaf_x - width * 0.08, center_y + height * 0.18),
                (leaf_x, center_y + height * 0.34),
                (leaf_x + width * 0.08, center_y + height * 0.18),
            ],
            stroke * 0.75,
        )
    return mask
```

- [ ] **Step 4: Wire scroll mask into `build_meshes`**

In `build_meshes`, after the text mask is converted to model coordinates and clipped to `occupied`, add:

```python
scroll_mask = np.zeros_like(occupied)
if text_enabled and args.top_scrolls:
    scroll_mask = make_top_scroll_mask(
        x_centers,
        y_centers,
        args.plate_width,
        args.plate_height,
        args.scroll_width,
        args.scroll_height,
        args.scroll_margin_x,
        args.scroll_margin_top,
    )
    scroll_mask &= occupied
    text_mask |= scroll_mask
```

In the no-text branch, keep `scroll_mask = np.zeros_like(occupied)`. In `meta`, add:

```python
"scroll_cells": int(scroll_mask.sum()),
```

- [ ] **Step 5: Add parser options**

In `parser()`, after `--pocket-clearance`, add:

```python
p.add_argument("--top-scrolls", action="store_true", help="Add second-color decorative scroll ornaments near the top.")
p.add_argument("--scroll-width", type=float, default=32.0)
p.add_argument("--scroll-height", type=float, default=12.0)
p.add_argument("--scroll-margin-x", type=float, default=14.0)
p.add_argument("--scroll-margin-top", type=float, default=8.0)
```

- [ ] **Step 6: Run tests to verify GREEN**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
```

Expected: all tests PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add work/plant_sign_generator/generate_plant_sign.py work/plant_sign_generator/test_generator.py
git commit -m "feat: add optional top scroll masks"
```

---

### Task 2: Public Script, Docs, And STL Outputs

**Files:**
- Modify: `outputs/plant_sign_generator.py`
- Modify: `README.md`
- Modify: `outputs/README.md`
- Regenerate: `outputs/plate_base.stl`
- Regenerate: `outputs/plate_text.stl`

**Interfaces:**
- Consumes: Task 1 CLI `--top-scrolls` and metadata `scroll_cells`.
- Produces: user-facing script/docs and regenerated example STL files with scrolls enabled.

- [ ] **Step 1: Sync public script**

Run:

```bash
cp work/plant_sign_generator/generate_plant_sign.py outputs/plant_sign_generator.py
```

- [ ] **Step 2: Update docs**

Add this example to `README.md` and `outputs/README.md` near the existing generation examples:

```bash
python3 outputs/plant_sign_generator.py --text "яблоня" --top-scrolls --outdir outputs
```

In `outputs/README.md`, add one sentence:

```markdown
Опция `--top-scrolls` добавляет два декоративных завитка сверху во второй цвет вместе с надписью.
```

- [ ] **Step 3: Regenerate example STL files**

Run:

```bash
python3 outputs/plant_sign_generator.py --text яблоня --top-scrolls --outdir outputs
```

Expected output includes:

```text
Generated outputs/plate_base.stl
Generated outputs/plate_text.stl
scroll_cells: <positive integer>
```

- [ ] **Step 4: Verify tests and STL files**

Run:

```bash
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/test_generator.py
/Users/antmat/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 work/plant_sign_generator/verify_stl.py outputs/plate_base.stl outputs/plate_text.stl
```

Expected: tests PASS; verifier prints dimensions and no bad-edge warnings.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add README.md outputs/README.md outputs/plant_sign_generator.py outputs/plate_base.stl outputs/plate_text.stl
git commit -m "feat: add top scroll example outputs"
git push origin main
```
