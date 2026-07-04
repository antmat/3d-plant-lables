#!/usr/bin/env python3
"""Focused regression tests for the plant sign generator."""

from __future__ import annotations

import os
import shutil
import subprocess

import numpy as np

import generate_plant_sign as gen


def bbox(mesh: gen.Mesh) -> tuple[np.ndarray, np.ndarray]:
    points = np.array([point for tri in mesh.triangles for point in tri], dtype=float)
    return points.min(axis=0), points.max(axis=0)


def non_manifold_edges(mesh: gen.Mesh) -> dict[tuple[tuple[float, float, float], tuple[float, float, float]], int]:
    edge_counts: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge = tuple(sorted((tuple(round(v, 5) for v in a), tuple(round(v, 5) for v in b))))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    return {edge: count for edge, count in edge_counts.items() if count != 2}


def connected_component_count(mesh: gen.Mesh) -> int:
    parent = list(range(len(mesh.triangles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    edge_to_triangles: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[int]] = {}
    for tri_index, tri in enumerate(mesh.triangles):
        points = [tuple(round(v, 5) for v in point) for point in tri]
        for a, b in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            edge = tuple(sorted((a, b)))
            edge_to_triangles.setdefault(edge, []).append(tri_index)

    for triangles in edge_to_triangles.values():
        first = triangles[0]
        for tri_index in triangles[1:]:
            union(first, tri_index)

    return len({find(index) for index in range(len(mesh.triangles))})


def horizontal_center_triangles(mesh: gen.Mesh, z: float, radius: float = 2.0) -> list[gen.Tri]:
    triangles = []
    for tri in mesh.triangles:
        if not all(abs(point[2] - z) < 1e-5 for point in tri):
            continue
        centroid = np.array(tri, dtype=float).mean(axis=0)
        if abs(float(centroid[0])) <= radius and abs(float(centroid[1])) <= radius:
            triangles.append(tri)
    return triangles


def test_image_mask_top_row_maps_to_model_top_row() -> None:
    image_mask = np.zeros((5, 4), dtype=bool)
    image_mask[0, 2] = True

    model_mask = gen.image_mask_to_model_mask(image_mask)

    assert model_mask[4, 2]
    assert model_mask.sum() == 1


def test_default_mesh_is_oriented_face_down_for_printing() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, text, _, _ = gen.build_meshes(args)

    base_min, base_max = bbox(base)
    text_min, text_max = bbox(text)

    assert min(base_min[2], text_min[2]) >= -0.001
    assert text_min[2] <= 0.001
    assert text_max[2] <= args.text_depth + 0.001
    assert abs((base_max[2] - base_min[2]) - args.plate_thickness) < 0.001


def test_default_base_mesh_has_manifold_edges() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, _, _, _ = gen.build_meshes(args)

    bad_edges = non_manifold_edges(base)

    assert bad_edges == {}


def test_default_text_mesh_has_manifold_edges() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    _, text, _, _ = gen.build_meshes(args)

    bad_edges = non_manifold_edges(text)

    assert bad_edges == {}


def test_public_generator_runs_with_default_python() -> None:
    default_python = shutil.which("python3")
    if not default_python:
        raise AssertionError("python3 was not found on PATH")

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = os.path.join(root, "outputs", "plant_sign_generator.py")
    result = subprocess.run(
        [default_python, script, "--help"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "Generate aligned STL files" in result.stdout


def test_resolve_text_reads_stdin_when_text_omitted() -> None:
    args = gen.parser().parse_args([])

    text = gen.resolve_text(args, stdin_text="яблоня\nMalus domestica\n")

    assert text == "яблоня\nMalus domestica"


def test_resolve_text_uses_default_when_text_omitted_and_stdin_empty() -> None:
    args = gen.parser().parse_args([])

    text = gen.resolve_text(args, stdin_text="")

    assert text == "яблоня"


def test_multiline_text_with_line_sizes_generates_two_line_mask() -> None:
    args = gen.parser().parse_args([
        "--text",
        "яблоня\nMalus domestica",
        "--line-size",
        "22",
        "--line-size",
        "8",
        "--outdir",
        "outputs",
    ])
    base, text, _, meta = gen.build_meshes(args)
    text_min, text_max = bbox(text)

    assert meta["line_count"] == 2
    assert text_max[1] - text_min[1] > 20.0
    assert non_manifold_edges(base) == {}
    assert non_manifold_edges(text) == {}


def test_multiline_text_accepts_per_line_fonts() -> None:
    georgia = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
    args = gen.parser().parse_args([
        "--text",
        "яблоня\nMalus domestica",
        "--line-font",
        "/Library/Fonts/YS Text-Heavy.ttf",
        "--line-font",
        georgia,
        "--outdir",
        "outputs",
    ])
    _, _, _, meta = gen.build_meshes(args)

    assert meta["line_count"] == 2
    assert georgia in meta["font_paths"]


def test_top_scrolls_default_off() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    _, _, _, meta = gen.build_meshes(args)

    assert int(meta["scroll_cells"]) == 0


def test_top_scrolls_add_second_color_geometry_near_top_corners() -> None:
    args_plain = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs", "--orientation", "front-up"])
    _, text_plain, _, meta_plain = gen.build_meshes(args_plain)
    try:
        args_scrolls = gen.parser().parse_args([
            "--text",
            "яблоня",
            "--top-scrolls",
            "--outdir",
            "outputs",
            "--orientation",
            "front-up",
        ])
    except SystemExit as exc:
        raise AssertionError("--top-scrolls should be accepted") from exc

    base_scrolls, text_scrolls, _, meta_scrolls = gen.build_meshes(args_scrolls)
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


def test_all_top_scroll_styles_generate_corner_geometry() -> None:
    styles = ["classic", "double-spiral", "vine", "laurel", "tulip", "wave"]
    for style in styles:
        args = gen.parser().parse_args([
            "--text",
            "яблоня",
            "--top-scrolls",
            "--scroll-style",
            style,
            "--outdir",
            "outputs",
            "--orientation",
            "front-up",
        ])
        _, text, _, meta = gen.build_meshes(args)
        points = np.array([point for tri in text.triangles for point in tri], dtype=float)
        corner_y = args.plate_height / 2.0 - args.scroll_margin_top - args.scroll_height - 2.0
        left = points[
            (points[:, 0] < -args.plate_width / 2.0 + args.scroll_margin_x + args.scroll_width + 2.0)
            & (points[:, 1] > corner_y)
        ]
        right = points[
            (points[:, 0] > args.plate_width / 2.0 - args.scroll_margin_x - args.scroll_width - 2.0)
            & (points[:, 1] > corner_y)
        ]

        assert args.scroll_style == style
        assert int(meta["scroll_cells"]) > 0
        assert len(left) > 0
        assert len(right) > 0
        assert non_manifold_edges(text) == {}


def test_default_plate_uses_dovetail_holder() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, _, holder, meta = gen.build_meshes(args)
    base_min, base_max = bbox(base)
    holder_min, holder_max = bbox(holder)

    assert args.plate_thickness == 6.0
    assert args.holder_style == "dovetail"
    assert args.rod_diameter == 12.0
    assert args.rod_clearance == 0.6
    assert args.holder_outer_diameter == 20.0
    assert abs(float(meta["holder_length"]) - 78.0) < 0.001
    assert abs(float(meta["channel_diameter"]) - 12.6) < 0.001
    assert abs((base_max[2] - base_min[2]) - 6.0) < 0.001
    assert abs((holder_max[2] - holder_min[2]) - 78.0) < 0.5
    assert int(meta["socket_cells"]) > 0
    assert int(meta["holder_cells"]) > 0
    assert holder.triangles


def test_holder_channel_has_blind_end_on_print_bed() -> None:
    args = gen.parser().parse_args(["--no-text", "--outdir", "outputs"])
    _, _, holder, _ = gen.build_meshes(args)
    holder_min, holder_max = bbox(holder)

    bottom_center = horizontal_center_triangles(holder, float(holder_min[2]))
    top_center = horizontal_center_triangles(holder, float(holder_max[2]))

    assert bottom_center
    assert top_center == []


def test_dovetail_base_and_holder_are_manifold() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs", "--orientation", "front-up"])
    base, text, holder, meta = gen.build_meshes(args)

    assert text is not None
    assert non_manifold_edges(base) == {}
    assert non_manifold_edges(holder) == {}
    assert connected_component_count(base) == 1
    assert connected_component_count(holder) == 1
    assert int(meta["socket_cells"]) > 0


def test_dovetail_socket_is_open_at_bottom_and_closed_at_top() -> None:
    args = gen.parser().parse_args(["--no-text", "--outdir", "outputs", "--orientation", "front-up"])
    base, _, _, _ = gen.build_meshes(args)
    points = np.array([point for tri in base.triangles for point in tri], dtype=float)
    socket_width = gen.dovetail_width_at_depth(
        points[:, 2],
        args.dovetail_neck_width + 2.0 * args.dovetail_clearance,
        args.dovetail_head_width + 2.0 * args.dovetail_clearance,
        args.dovetail_depth,
    )
    rear_socket_points = points[
        (points[:, 1] < args.plate_height / 2.0 - 1.0)
        & (points[:, 2] > 0.1)
        & (points[:, 2] < args.dovetail_depth - 0.1)
        & (np.abs(np.abs(points[:, 0]) - socket_width / 2.0) < 0.45)
    ]

    assert rear_socket_points[:, 1].min() <= -args.plate_height / 2.0 + 0.5
    assert rear_socket_points[:, 1].max() < args.plate_height / 2.0 - args.holder_top_margin + 1.0


def test_no_text_builds_flat_plate_without_text_mesh() -> None:
    args = gen.parser().parse_args(["--no-text", "--outdir", "outputs"])
    base, text, holder, meta = gen.build_meshes(args)
    points = np.array([point for tri in base.triangles for point in tri], dtype=float)

    assert text is None
    assert holder.triangles
    assert meta["text_enabled"] is False
    assert int(meta["text_cells"]) == 0
    assert int(meta["pocket_cells"]) == 0
    assert (points[:, 2] < args.plate_thickness).any()
    front_plate_points = points[
        (points[:, 2] >= args.plate_thickness - 0.001)
        & (points[:, 2] <= args.plate_thickness + 0.001)
    ]
    assert len(front_plate_points) > 0


def test_no_text_cli_skips_and_removes_plate_text_stl() -> None:
    default_python = shutil.which("python3")
    if not default_python:
        raise AssertionError("python3 was not found on PATH")

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = os.path.join(root, "outputs", "plant_sign_generator.py")
    tmp = os.path.join(root, "work", "test-no-text-output")
    os.makedirs(tmp, exist_ok=True)
    stale_text = os.path.join(tmp, "plate_text.stl")
    with open(stale_text, "wb") as f:
        f.write(b"stale")

    result = subprocess.run(
        [default_python, script, "--no-text", "--outdir", tmp],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert os.path.exists(os.path.join(tmp, "plate_base.stl"))
    assert os.path.exists(os.path.join(tmp, "holder.stl"))
    assert not os.path.exists(stale_text)
    assert "Skipped" in result.stdout
    assert "Generated" in result.stdout
    assert "holder.stl" in result.stdout


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


def main() -> int:
    tests = [
        test_image_mask_top_row_maps_to_model_top_row,
        test_default_mesh_is_oriented_face_down_for_printing,
        test_default_base_mesh_has_manifold_edges,
        test_default_text_mesh_has_manifold_edges,
        test_public_generator_runs_with_default_python,
        test_resolve_text_reads_stdin_when_text_omitted,
        test_resolve_text_uses_default_when_text_omitted_and_stdin_empty,
        test_multiline_text_with_line_sizes_generates_two_line_mask,
        test_multiline_text_accepts_per_line_fonts,
        test_top_scrolls_default_off,
        test_top_scrolls_add_second_color_geometry_near_top_corners,
        test_all_top_scroll_styles_generate_corner_geometry,
        test_default_plate_uses_dovetail_holder,
        test_holder_channel_has_blind_end_on_print_bed,
        test_dovetail_base_and_holder_are_manifold,
        test_dovetail_socket_is_open_at_bottom_and_closed_at_top,
        test_no_text_builds_flat_plate_without_text_mesh,
        test_no_text_cli_skips_and_removes_plate_text_stl,
        test_cli_writes_holder_stl,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
