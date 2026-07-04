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
DEFAULT_TEXT = "яблоня"
FALLBACK_FONTS = [
    DEFAULT_FONT,
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
]


Vec3 = tuple[float, float, float]
Tri = tuple[Vec3, Vec3, Vec3]


@dataclass(frozen=True)
class TextLayout:
    mask: np.ndarray
    line_count: int
    font_paths: list[str]
    font_pixel_sizes: list[int]


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


def normalize_text(text: str) -> str:
    return text.replace("\\n", "\n").rstrip("\r\n")


def resolve_text(args: argparse.Namespace, stdin_text: str | None = None) -> str:
    if args.text == "-":
        text = sys.stdin.read() if stdin_text is None else stdin_text
        return normalize_text(text) or DEFAULT_TEXT
    if args.text is not None:
        return normalize_text(args.text) or DEFAULT_TEXT

    if stdin_text is None:
        stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    return normalize_text(stdin_text) or DEFAULT_TEXT


def repeated_option(values: list[object] | None, index: int, default: object) -> object:
    if not values:
        return default
    return values[index] if index < len(values) else values[-1]


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


def measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    fonts: list[ImageFont.FreeTypeFont],
    line_spacing: float,
) -> tuple[list[tuple[int, int, int, int]], int, int, list[int]]:
    bboxes = []
    heights = []
    max_width = 0
    for line, font in zip(lines, fonts):
        bbox = draw.textbbox((0, 0), line if line else " ", font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1] if line else max(1, font.size)
        bboxes.append(bbox)
        heights.append(height)
        max_width = max(max_width, width)

    gaps = []
    for idx in range(max(0, len(lines) - 1)):
        larger = max(fonts[idx].size, fonts[idx + 1].size)
        gaps.append(max(0, int(round(larger * (line_spacing - 1.0)))))
    total_height = sum(heights) + sum(gaps)
    return bboxes, max_width, total_height, gaps


def fit_multiline_fonts(
    lines: list[str],
    font_paths: list[str],
    max_w: int,
    max_h: int,
    line_spacing: float,
) -> list[ImageFont.FreeTypeFont]:
    probe = Image.new("L", (10, 10))
    draw = ImageDraw.Draw(probe)
    lo, hi = 1, max(8, max_h * 2)
    best = [ImageFont.truetype(path, lo) for path in font_paths]
    while lo <= hi:
        mid = (lo + hi) // 2
        fonts = [ImageFont.truetype(path, mid) for path in font_paths]
        _, width, height, _ = measure_lines(draw, lines, fonts, line_spacing)
        if width <= max_w and height <= max_h:
            best = fonts
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def fonts_from_line_sizes(
    line_sizes: list[float],
    font_paths: list[str],
    px_per_mm: float,
    max_w: int,
    max_h: int,
    lines: list[str],
    line_spacing: float,
) -> list[ImageFont.FreeTypeFont]:
    sizes_px = [max(1, int(round(size_mm * px_per_mm))) for size_mm in line_sizes]
    probe = Image.new("L", (10, 10))
    draw = ImageDraw.Draw(probe)
    fonts = [ImageFont.truetype(path, px) for path, px in zip(font_paths, sizes_px)]
    _, width, height, _ = measure_lines(draw, lines, fonts, line_spacing)
    if width <= max_w and height <= max_h:
        return fonts

    scale = min(max_w / max(width, 1), max_h / max(height, 1))
    scaled_sizes = [max(1, int(math.floor(px * scale))) for px in sizes_px]
    return [ImageFont.truetype(path, px) for path, px in zip(font_paths, scaled_sizes)]


def render_text_layout(
    text: str,
    font_path: str,
    line_fonts: list[str] | None,
    line_sizes: list[float] | None,
    nx: int,
    ny: int,
    plate_width: float,
    plate_height: float,
    margin_x: float,
    margin_y: float,
    line_spacing: float,
    antialias: int,
    threshold: int,
) -> TextLayout:
    scale = max(1, antialias)
    w_px = nx * scale
    h_px = ny * scale
    max_w = int((plate_width - 2.0 * margin_x) / plate_width * w_px)
    max_h = int((plate_height - 2.0 * margin_y) / plate_height * h_px)
    lines = text.split("\n") or [DEFAULT_TEXT]
    font_paths = [
        existing_font(str(repeated_option(line_fonts, index, font_path)))
        for index in range(len(lines))
    ]

    img = Image.new("L", (w_px, h_px), 0)
    draw = ImageDraw.Draw(img)
    if line_sizes:
        physical_sizes = [
            float(repeated_option(line_sizes, index, line_sizes[-1]))
            for index in range(len(lines))
        ]
        fonts = fonts_from_line_sizes(
            physical_sizes,
            font_paths,
            (w_px / plate_width),
            max_w,
            max_h,
            lines,
            line_spacing,
        )
    else:
        fonts = fit_multiline_fonts(lines, font_paths, max_w, max_h, line_spacing)

    bboxes, width, height, gaps = measure_lines(draw, lines, fonts, line_spacing)
    y = (h_px - height) / 2.0
    for index, (line, font, bbox) in enumerate(zip(lines, fonts, bboxes)):
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1] if line else max(1, font.size)
        if line:
            x = (w_px - line_width) / 2.0 - bbox[0]
            draw.text((x, y - bbox[1]), line, fill=255, font=font)
        if index < len(gaps):
            y += line_height + gaps[index]

    if scale != 1:
        img = img.resize((nx, ny), Image.Resampling.LANCZOS)
    return TextLayout(
        mask=np.asarray(img) >= threshold,
        line_count=len(lines),
        font_paths=font_paths,
        font_pixel_sizes=[font.size for font in fonts],
    )


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


def add_extruded_polygon_y(
    mesh: Mesh,
    polygon_xz: list[tuple[float, float]],
    y_min: float,
    y_max: float,
) -> int:
    start_count = len(mesh.triangles)
    bottom = [(x, y_min, z) for x, z in polygon_xz]
    top = [(x, y_max, z) for x, z in polygon_xz]
    count = len(polygon_xz)
    for index in range(count):
        nxt = (index + 1) % count
        mesh.quad(bottom[index], bottom[nxt], top[nxt], top[index])

    center_bottom = (
        sum(x for x, _ in polygon_xz) / count,
        y_min,
        sum(z for _, z in polygon_xz) / count,
    )
    center_top = (center_bottom[0], y_max, center_bottom[2])
    for index in range(count):
        nxt = (index + 1) % count
        mesh.tri(center_bottom, bottom[nxt], bottom[index])
        mesh.tri(center_top, top[index], top[nxt])
    return len(mesh.triangles) - start_count


def add_holder_transition_y(
    mesh: Mesh,
    holder_radius: float,
    holder_center_z: float,
    plate_overlap: float,
    cylinder_overlap: float,
    y_min: float,
    y_max: float,
    segments: int,
) -> int:
    if holder_radius <= 0:
        return 0
    if abs(holder_center_z) >= holder_radius:
        return 0

    contact_x = math.sqrt(holder_radius * holder_radius - holder_center_z * holder_center_z)
    start_x = max(0.0, contact_x - cylinder_overlap)
    end_x = holder_radius
    if end_x <= start_x:
        return 0

    sample_count = max(3, segments)
    xs = [start_x + (end_x - start_x) * index / (sample_count - 1) for index in range(sample_count)]
    bottom = [
        (
            x,
            holder_center_z + math.sqrt(max(holder_radius * holder_radius - x * x, 0.0)) - cylinder_overlap,
        )
        for x in xs
    ]
    top_z = plate_overlap
    positive = [(start_x, top_z), (end_x, top_z), *reversed(bottom)]
    negative = [(-x, z) for x, z in reversed(positive)]
    return (
        add_extruded_polygon_y(mesh, positive, y_min, y_max)
        + add_extruded_polygon_y(mesh, negative, y_min, y_max)
    )


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

    args.text = args.text or DEFAULT_TEXT
    font = existing_font(args.font)
    occupied = rounded_rect_occupancy(x_centers, y_centers, args.plate_width, args.plate_height, args.corner_radius)
    text_layout = render_text_layout(
        args.text,
        font,
        args.line_font,
        args.line_size,
        nx,
        ny,
        args.plate_width,
        args.plate_height,
        args.text_margin_x,
        args.text_margin_y,
        args.line_spacing,
        args.antialias,
        args.text_threshold,
    )
    text_mask = text_layout.mask
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

    transition_y_min = y_min + args.transition_end_margin
    transition_y_max = y_max - args.transition_end_margin
    transition_triangles = add_holder_transition_y(
        base,
        holder_outer,
        holder_center_z,
        args.transition_plate_overlap,
        args.transition_cylinder_overlap,
        transition_y_min,
        transition_y_max,
        args.transition_segments,
    )

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
        "transition_triangles": transition_triangles,
        "transition_length": transition_y_max - transition_y_min,
        "line_count": text_layout.line_count,
        "font_paths": ", ".join(text_layout.font_paths),
        "font_pixel_sizes": ", ".join(str(size) for size in text_layout.font_pixel_sizes),
    }
    return base, text, meta


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate two aligned STL files for a plant sign.")
    p.add_argument("--text", default=None, help="Text to put on the sign. Use '-' to read stdin.")
    p.add_argument("--outdir", default="outputs", help="Directory for plate_base.stl and plate_text.stl.")
    p.add_argument("--font", default=DEFAULT_FONT, help="Path to a TTF/OTF font with Cyrillic support.")
    p.add_argument("--line-font", action="append", default=None, help="Repeatable per-line font path. Last value repeats.")
    p.add_argument("--line-size", action="append", type=float, default=None, help="Repeatable per-line font size in mm. Last value repeats.")
    p.add_argument("--line-spacing", type=float, default=1.18, help="Line spacing multiplier.")
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
    p.add_argument("--rod-diameter", type=float, default=12.0)
    p.add_argument("--rod-clearance", type=float, default=0.6)
    p.add_argument("--holder-outer-diameter", type=float, default=20.0)
    p.add_argument("--holder-length", type=float, default=65.0)
    p.add_argument("--holder-cap-thickness", type=float, default=4.0)
    p.add_argument("--holder-embed", type=float, default=2.0)
    p.add_argument("--holder-segments", type=int, default=96)
    p.add_argument("--transition-plate-overlap", type=float, default=0.8)
    p.add_argument("--transition-cylinder-overlap", type=float, default=0.4)
    p.add_argument("--transition-end-margin", type=float, default=0.0)
    p.add_argument("--transition-segments", type=int, default=28)
    p.add_argument("--orientation", choices=["face-down", "front-up"], default="face-down")
    return p


def main() -> None:
    args = parser().parse_args()
    args.text = resolve_text(args)
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
