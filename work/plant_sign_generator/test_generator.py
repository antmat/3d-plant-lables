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


def test_image_mask_top_row_maps_to_model_top_row() -> None:
    image_mask = np.zeros((5, 4), dtype=bool)
    image_mask[0, 2] = True

    model_mask = gen.image_mask_to_model_mask(image_mask)

    assert model_mask[4, 2]
    assert model_mask.sum() == 1


def test_default_mesh_is_oriented_face_down_for_printing() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, text, _ = gen.build_meshes(args)

    base_min, base_max = bbox(base)
    text_min, text_max = bbox(text)

    assert min(base_min[2], text_min[2]) >= -0.001
    assert text_min[2] <= 0.001
    assert text_max[2] <= args.text_depth + 0.001
    assert base_max[2] > args.plate_thickness + args.holder_outer_diameter - args.holder_embed - 1.0


def test_default_base_mesh_has_manifold_edges() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    base, _, _ = gen.build_meshes(args)

    bad_edges = non_manifold_edges(base)

    assert bad_edges == {}


def test_default_text_mesh_has_manifold_edges() -> None:
    args = gen.parser().parse_args(["--text", "яблоня", "--outdir", "outputs"])
    _, text, _ = gen.build_meshes(args)

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
    assert "Generate two aligned STL files" in result.stdout


def main() -> int:
    tests = [
        test_image_mask_top_row_maps_to_model_top_row,
        test_default_mesh_is_oriented_face_down_for_printing,
        test_default_base_mesh_has_manifold_edges,
        test_default_text_mesh_has_manifold_edges,
        test_public_generator_runs_with_default_python,
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
