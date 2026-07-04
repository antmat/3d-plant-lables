#!/usr/bin/env python3
"""Print triangle counts and bounding boxes for binary STL files."""

from __future__ import annotations

import os
import struct
import sys

import numpy as np


def inspect(path: str) -> tuple[int, np.ndarray, np.ndarray]:
    size = os.path.getsize(path)
    if size < 84:
        raise ValueError(f"{path}: file is too small for binary STL")

    with open(path, "rb") as f:
        f.seek(80)
        tri_count = struct.unpack("<I", f.read(4))[0]
        expected = 84 + tri_count * 50
        if size != expected:
            raise ValueError(f"{path}: size {size} does not match {tri_count} binary STL triangles")

        mins = np.array([float("inf"), float("inf"), float("inf")])
        maxs = np.array([float("-inf"), float("-inf"), float("-inf")])
        for _ in range(tri_count):
            record = f.read(50)
            values = struct.unpack("<12fH", record)
            coords = np.array(values[3:12], dtype=float).reshape(3, 3)
            mins = np.minimum(mins, coords.min(axis=0))
            maxs = np.maximum(maxs, coords.max(axis=0))

    return tri_count, mins, maxs


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: verify_stl.py FILE.stl [FILE.stl ...]", file=sys.stderr)
        return 2

    for path in argv[1:]:
        tri_count, mins, maxs = inspect(path)
        dims = maxs - mins
        print(path)
        print(f"  triangles: {tri_count}")
        print(f"  min: x={mins[0]:.3f} y={mins[1]:.3f} z={mins[2]:.3f}")
        print(f"  max: x={maxs[0]:.3f} y={maxs[1]:.3f} z={maxs[2]:.3f}")
        print(f"  size: x={dims[0]:.3f} y={dims[1]:.3f} z={dims[2]:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
