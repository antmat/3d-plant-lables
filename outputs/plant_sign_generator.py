#!/usr/bin/env python3
"""Generate aligned STL parts for a two-color plant sign."""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import struct
import sys
from dataclasses import dataclass, field
from typing import Iterable


REQUIRED_MODULES = {
    "numpy": "numpy",
    "PIL": "Pillow",
}
BUNDLED_PYTHON = os.path.expanduser(
    "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)


def missing_dependencies() -> list[str]:
    missing = []
    for module_name, package_name in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def ensure_dependencies() -> None:
    missing = missing_dependencies()
    if not missing:
        return

    current = os.path.realpath(sys.executable)
    bundled = os.path.realpath(BUNDLED_PYTHON)
    if os.path.exists(BUNDLED_PYTHON) and current != bundled:
        os.execv(BUNDLED_PYTHON, [BUNDLED_PYTHON, *sys.argv])

    packages = " ".join(sorted(set(missing)))
    raise SystemExit(
        "Missing Python dependencies: "
        + packages
        + "\nInstall them with:\n"
        + f"  {sys.executable} -m pip install {packages}\n"
        + "or run with the bundled Codex Python:\n"
        + f"  {BUNDLED_PYTHON} {sys.argv[0]}"
    )


ensure_dependencies()

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


DEFAULT_FONT = "/Library/Fonts/YS Text-Heavy.ttf"
FALLBACK_FONTS = [
    DEFAULT_FONT,
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
]


Vec3 = tuple[float, float, float]
Tri = tuple[Vec3, Vec3, Vec3]


@dataclass
class Mesh:
    name: str
    triangles: list[Tri] = field(default_factory=list)

    def tri(self, a: Vec3, b: Vec3, c: Vec3) -> None:
        self.triangles.append((a, b, c))

    def quad(self, a: Vec3, b: Vec3, c: Vec3, d: Vec3) -> None:
        self.tri(a, b, c)
        self.tri(a, c, d)

    def extend(self, other: "Mesh") -> None:
        self.triangles.extend(other.triangles)


def normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def write_binary_stl(mesh: Mesh, path: str) -> None:
    header = mesh.name.encode("utf-8", errors="ignore")[:80].ljust(80, b"\0")
    with open(path, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(mesh.triangles)))
        for a, b, c in mesh.triangles:
            n = normal(a, b, c)
            f.write(struct.pack("<12fH", *n, *a, *b, *c, 0))


def existing_font(preferred: str) -> str:
    candidates = [preferred, *FALLBACK_FONTS]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError("No usable TrueType/OpenType font found")


def rounded_rect_occupancy(
    x_centers: np.ndarray,
    y_centers: np.ndarray,
    width: float,
    height: float,
    radius: float,
) -> np.ndarray:
    xx, yy = np.meshgrid(x_centers, y_centers)
    ax = np.abs(xx)
    ay = np.abs(yy)
    inner_x = width / 2.0 - radius
    inner_y = height / 2.0 - radius
    core = (ax <= inner_x) | (ay <= inner_y)
    corner_dx = np.maximum(ax - inner_x, 0.0)
    corner_dy = np.maximum(ay - inner_y, 0.0)
    corners = corner_dx * corner_dx + corner_dy * corner_dy <= radius * radius
    return core | corners


def fit_font(text: str, font_path: str, max_w: int, max_h: int) -> ImageFont.FreeTypeFont:
    probe = Image.new("L", (10, 10))
    draw = ImageDraw.Draw(probe)
    lo, hi = 1, max(8, max_h * 2)
    best = ImageFont.truetype(font_path, lo)
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_w and bottom - top <= max_h:
            best = font
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def render_text_mask(
    text: str,
    font_path: str,
    nx: int,
    ny: int,
    plate_width: float,
    plate_height: float,
    margin_x: float,
    margin_y: float,
    antialias: int,
    threshold: int,
) -> np.ndarray:
    scale = max(1, antialias)
    w_px = nx * scale
    h_px = ny * scale
    max_w = int((plate_width - 2.0 * margin_x) / plate_width * w_px)
    max_h = int((plate_height - 2.0 * margin_y) / plate_height * h_px)
    font = fit_font(text, font_path, max_w, max_h)

    img = Image.new("L", (w_px, h_px), 0)
    draw = ImageDraw.Draw(img)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w = right - left
    text_h = bottom - top
    x = (w_px - text_w) / 2.0 - left
    y = (h_px - text_h) / 2.0 - top
    draw.text((x, y), text, fill=255, font=font)

    if scale != 1:
        img = img.resize((nx, ny), Image.Resampling.LANCZOS)
    return np.asarray(img) >= threshold


def dilate_mask(mask: np.ndarray, clearance_mm: float, resolution_mm: float) -> np.ndarray:
    if clearance_mm <= 0:
        return mask
    radius_px = max(1, int(math.ceil(clearance_mm / resolution_mm)))
    size = radius_px * 2 + 1
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    dilated = img.filter(ImageFilter.MaxFilter(size=size))
    return np.asarray(dilated) > 0


def image_mask_to_model_mask(mask: np.ndarray) -> np.ndarray:
    return np.flipud(mask)


def fill_diagonal_contacts(mask: np.ndarray) -> np.ndarray:
    fixed = mask.copy()
    while True:
        diagonal_a = fixed[:-1, :-1] & fixed[1:, 1:] & ~fixed[:-1, 1:] & ~fixed[1:, :-1]
        diagonal_b = fixed[:-1, 1:] & fixed[1:, :-1] & ~fixed[:-1, :-1] & ~fixed[1:, 1:]
        if not diagonal_a.any() and not diagonal_b.any():
            return fixed
        rows_a, cols_a = np.nonzero(diagonal_a)
        rows_b, cols_b = np.nonzero(diagonal_b)
        fixed[rows_a, cols_a + 1] = True
        fixed[rows_a + 1, cols_a] = True
        fixed[rows_b, cols_b] = True
        fixed[rows_b + 1, cols_b + 1] = True


def transform_mesh(mesh: Mesh, transform) -> None:
    mesh.triangles = [
        (transform(a), transform(b), transform(c))
        for a, b, c in mesh.triangles
    ]


def orient_face_down(meshes: Iterable[Mesh], front_z: float) -> None:
    def transform(p: Vec3) -> Vec3:
        return (p[0], -p[1], front_z - p[2])

    for mesh in meshes:
        transform_mesh(mesh, transform)


def cell_corners(x_edges: np.ndarray, y_edges: np.ndarray, i: int, j: int, z: float) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    x0, x1 = float(x_edges[i]), float(x_edges[i + 1])
    y0, y1 = float(y_edges[j]), float(y_edges[j + 1])
    return (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)


def add_box_cell(mesh: Mesh, x_edges: np.ndarray, y_edges: np.ndarray, i: int, j: int, z0: float, z1: float, mask: np.ndarray) -> None:
    p00, p10, p11, p01 = cell_corners(x_edges, y_edges, i, j, z1)
    b00, b10, b11, b01 = cell_corners(x_edges, y_edges, i, j, z0)
    mesh.quad(p00, p10, p11, p01)
    mesh.quad(b00, b01, b11, b10)

    ny, nx = mask.shape
    neighbors = [
        (i, j - 1, b00, b10, p10, p00),
        (i + 1, j, b10, b11, p11, p10),
        (i, j + 1, b11, b01, p01, p11),
        (i - 1, j, b01, b00, p00, p01),
    ]
    for ni, nj, a, b, c, d in neighbors:
        if ni < 0 or nj < 0 or ni >= nx or nj >= ny or not mask[nj, ni]:
            mesh.quad(a, b, c, d)


def add_heightfield_plate(
    mesh: Mesh,
    occupied: np.ndarray,
    pocket: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    plate_thickness: float,
    text_depth: float,
) -> None:
    ny, nx = occupied.shape
    high = plate_thickness
    low = plate_thickness - text_depth

    for j in range(ny):
        for i in range(nx):
            if not occupied[j, i]:
                continue
            z = low if pocket[j, i] else high
            p00, p10, p11, p01 = cell_corners(x_edges, y_edges, i, j, z)
            b00, b10, b11, b01 = cell_corners(x_edges, y_edges, i, j, 0.0)
            mesh.quad(p00, p10, p11, p01)
            mesh.quad(b00, b01, b11, b10)

            sides = [
                (i, j - 1, b00, b10, p10, p00, "south"),
                (i + 1, j, b10, b11, p11, p10, "east"),
                (i, j + 1, b11, b01, p01, p11, "north"),
                (i - 1, j, b01, b00, p00, p01, "west"),
            ]
            for ni, nj, a0, b0, b1, a1, edge in sides:
                if ni < 0 or nj < 0 or ni >= nx or nj >= ny or not occupied[nj, ni]:
                    mesh.quad(a0, b0, b1, a1)
                    continue

                if edge not in ("east", "north"):
                    continue
                neighbor_z = low if pocket[nj, ni] else high
                if abs(neighbor_z - z) < 1e-9:
                    continue
                z_min, z_max = sorted((z, neighbor_z))
                if edge == "south":
                    a = (float(x_edges[i]), float(y_edges[j]), z_min)
                    b = (float(x_edges[i + 1]), float(y_edges[j]), z_min)
                    c = (float(x_edges[i + 1]), float(y_edges[j]), z_max)
                    d = (float(x_edges[i]), float(y_edges[j]), z_max)
                elif edge == "east":
                    a = (float(x_edges[i + 1]), float(y_edges[j]), z_min)
                    b = (float(x_edges[i + 1]), float(y_edges[j + 1]), z_min)
                    c = (float(x_edges[i + 1]), float(y_edges[j + 1]), z_max)
                    d = (float(x_edges[i + 1]), float(y_edges[j]), z_max)
                elif edge == "north":
                    a = (float(x_edges[i + 1]), float(y_edges[j + 1]), z_min)
                    b = (float(x_edges[i]), float(y_edges[j + 1]), z_min)
                    c = (float(x_edges[i]), float(y_edges[j + 1]), z_max)
                    d = (float(x_edges[i + 1]), float(y_edges[j + 1]), z_max)
                else:
                    a = (float(x_edges[i]), float(y_edges[j + 1]), z_min)
                    b = (float(x_edges[i]), float(y_edges[j]), z_min)
                    c = (float(x_edges[i]), float(y_edges[j]), z_max)
                    d = (float(x_edges[i]), float(y_edges[j + 1]), z_max)
                mesh.quad(a, b, c, d)


def add_mask_solid(
    mesh: Mesh,
    mask: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    z0: float,
    z1: float,
) -> None:
    ny, nx = mask.shape
    for j in range(ny):
        for i in range(nx):
            if not mask[j, i]:
                continue
            add_box_cell(mesh, x_edges, y_edges, i, j, z0, z1, mask)


def ring_points_y(radius_x: float, radius_z: float, center_x: float, center_z: float, y: float, segments: int) -> list[Vec3]:
    return [
        (
            center_x + radius_x * math.cos(2.0 * math.pi * k / segments),
            y,
            center_z + radius_z * math.sin(2.0 * math.pi * k / segments),
        )
        for k in range(segments)
    ]


def add_solid_ellipse_y(
    mesh: Mesh,
    center_x: float,
    center_z: float,
    radius_x: float,
    radius_z: float,
    y_min: float,
    y_max: float,
    segments: int,
) -> None:
    bottom = ring_points_y(radius_x, radius_z, center_x, center_z, y_min, segments)
    top = ring_points_y(radius_x, radius_z, center_x, center_z, y_max, segments)
    c_bottom = (center_x, y_min, center_z)
    c_top = (center_x, y_max, center_z)
    for k in range(segments):
        n = (k + 1) % segments
        mesh.quad(bottom[k], bottom[n], top[n], top[k])
        mesh.tri(c_top, top[k], top[n])
        mesh.tri(c_bottom, bottom[n], bottom[k])


def add_blind_tube_y(
    mesh: Mesh,
    outer_radius: float,
    inner_radius: float,
    center_z: float,
    y_min: float,
    y_max: float,
    cap_thickness: float,
    segments: int,
) -> None:
    outer_bottom = ring_points_y(outer_radius, outer_radius, 0.0, center_z, y_min, segments)
    outer_top = ring_points_y(outer_radius, outer_radius, 0.0, center_z, y_max, segments)
    inner_bottom = ring_points_y(inner_radius, inner_radius, 0.0, center_z, y_min, segments)
    inner_top_y = y_max - cap_thickness
    inner_top = ring_points_y(inner_radius, inner_radius, 0.0, center_z, inner_top_y, segments)
    c_outer_top = (0.0, y_max, center_z)
    c_inner_top = (0.0, inner_top_y, center_z)

    for k in range(segments):
        n = (k + 1) % segments
        mesh.quad(outer_bottom[k], outer_bottom[n], outer_top[n], outer_top[k])
        mesh.tri(c_outer_top, outer_top[k], outer_top[n])
        mesh.quad(outer_bottom[n], outer_bottom[k], inner_bottom[k], inner_bottom[n])
        mesh.quad(inner_bottom[k], inner_top[k], inner_top[n], inner_bottom[n])
        mesh.tri(c_inner_top, inner_top[n], inner_top[k])


def build_meshes(args: argparse.Namespace) -> tuple[Mesh, Mesh, dict[str, object]]:
    nx = int(round(args.plate_width / args.resolution))
    ny = int(round(args.plate_height / args.resolution))
    x_edges = np.linspace(-args.plate_width / 2.0, args.plate_width / 2.0, nx + 1)
    y_edges = np.linspace(-args.plate_height / 2.0, args.plate_height / 2.0, ny + 1)
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2.0
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2.0

    font = existing_font(args.font)
    occupied = rounded_rect_occupancy(x_centers, y_centers, args.plate_width, args.plate_height, args.corner_radius)
    text_mask = render_text_mask(
        args.text,
        font,
        nx,
        ny,
        args.plate_width,
        args.plate_height,
        args.text_margin_x,
        args.text_margin_y,
        args.antialias,
        args.text_threshold,
    )
    text_mask = image_mask_to_model_mask(text_mask)
    text_mask &= occupied
    text_mask = fill_diagonal_contacts(text_mask) & occupied
    pocket_mask = dilate_mask(text_mask, args.pocket_clearance, args.resolution) & occupied

    base = Mesh("plant_sign_base")
    add_heightfield_plate(base, occupied, pocket_mask, x_edges, y_edges, args.plate_thickness, args.text_depth)

    holder_outer = args.holder_outer_diameter / 2.0
    holder_inner = args.rod_diameter / 2.0 + args.rod_clearance / 2.0
    holder_center_z = -holder_outer + args.holder_embed
    y_min = -args.holder_length / 2.0
    y_max = args.holder_length / 2.0
    add_blind_tube_y(
        base,
        holder_outer,
        holder_inner,
        holder_center_z,
        y_min,
        y_max,
        args.holder_cap_thickness,
        args.holder_segments,
    )

    rib_y_min = y_min + args.rib_end_margin
    rib_y_max = y_max - args.rib_end_margin
    add_solid_ellipse_y(base, -args.rib_offset_x, -args.rib_depth, args.rib_radius_x, args.rib_radius_z, rib_y_min, rib_y_max, args.rib_segments)
    add_solid_ellipse_y(base, args.rib_offset_x, -args.rib_depth, args.rib_radius_x, args.rib_radius_z, rib_y_min, rib_y_max, args.rib_segments)

    text = Mesh("plant_sign_text")
    add_mask_solid(
        text,
        text_mask,
        x_edges,
        y_edges,
        args.plate_thickness - args.text_depth,
        args.plate_thickness + args.text_proud,
    )

    if args.orientation == "face-down":
        orient_face_down([base, text], args.plate_thickness + max(args.text_proud, 0.0))

    meta = {
        "font": font,
        "grid": f"{nx} x {ny}",
        "text_cells": int(text_mask.sum()),
        "pocket_cells": int(pocket_mask.sum()),
        "base_triangles": len(base.triangles),
        "text_triangles": len(text.triangles),
        "channel_diameter": holder_inner * 2.0,
        "orientation": args.orientation,
    }
    return base, text, meta


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate two aligned STL files for a plant sign.")
    p.add_argument("--text", default="яблоня", help="Text to put on the sign.")
    p.add_argument("--outdir", default="outputs", help="Directory for plate_base.stl and plate_text.stl.")
    p.add_argument("--font", default=DEFAULT_FONT, help="Path to a TTF/OTF font with Cyrillic support.")
    p.add_argument("--plate-width", type=float, default=180.0)
    p.add_argument("--plate-height", type=float, default=90.0)
    p.add_argument("--plate-thickness", type=float, default=4.0)
    p.add_argument("--corner-radius", type=float, default=4.0)
    p.add_argument("--resolution", type=float, default=0.4, help="XY mesh cell size in mm.")
    p.add_argument("--text-depth", type=float, default=0.8)
    p.add_argument("--text-proud", type=float, default=0.0)
    p.add_argument("--text-margin-x", type=float, default=14.0)
    p.add_argument("--text-margin-y", type=float, default=20.0)
    p.add_argument("--text-threshold", type=int, default=110)
    p.add_argument("--antialias", type=int, default=3)
    p.add_argument("--pocket-clearance", type=float, default=0.0)
    p.add_argument("--rod-diameter", type=float, default=8.0)
    p.add_argument("--rod-clearance", type=float, default=0.6)
    p.add_argument("--holder-outer-diameter", type=float, default=16.0)
    p.add_argument("--holder-length", type=float, default=65.0)
    p.add_argument("--holder-cap-thickness", type=float, default=4.0)
    p.add_argument("--holder-embed", type=float, default=2.0)
    p.add_argument("--holder-segments", type=int, default=96)
    p.add_argument("--rib-offset-x", type=float, default=5.8)
    p.add_argument("--rib-depth", type=float, default=2.4)
    p.add_argument("--rib-radius-x", type=float, default=3.4)
    p.add_argument("--rib-radius-z", type=float, default=2.8)
    p.add_argument("--rib-end-margin", type=float, default=4.0)
    p.add_argument("--rib-segments", type=int, default=32)
    p.add_argument("--orientation", choices=["face-down", "front-up"], default="face-down")
    return p


def main() -> None:
    args = parser().parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    base, text, meta = build_meshes(args)

    base_path = os.path.join(args.outdir, "plate_base.stl")
    text_path = os.path.join(args.outdir, "plate_text.stl")
    write_binary_stl(base, base_path)
    write_binary_stl(text, text_path)

    print(f"Generated {base_path}")
    print(f"Generated {text_path}")
    for key, value in meta.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
