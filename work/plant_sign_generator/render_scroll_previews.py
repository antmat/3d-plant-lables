#!/usr/bin/env python3
"""Render numbered PNG previews for all top-scroll styles."""

from __future__ import annotations

import argparse
import math
import os

import generate_plant_sign as gen

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render numbered preview PNGs for all top-scroll styles.")
    p.add_argument("--text", "-text", default="Лобо\n\n2023")
    p.add_argument("--outdir", default=os.path.join("outputs", "scroll_previews"))
    p.add_argument("--font", default=gen.DEFAULT_FONT)
    p.add_argument("--line-font", action="append", default=None)
    p.add_argument("--line-size", action="append", type=float, default=None)
    p.add_argument("--line-spacing", type=float, default=1.18)
    p.add_argument("--plate-width", type=float, default=180.0)
    p.add_argument("--plate-height", type=float, default=90.0)
    p.add_argument("--corner-radius", type=float, default=4.0)
    p.add_argument("--text-margin-x", type=float, default=14.0)
    p.add_argument("--text-margin-y", type=float, default=20.0)
    p.add_argument("--text-threshold", type=int, default=110)
    p.add_argument("--antialias", type=int, default=3)
    p.add_argument("--scroll-width", type=float, default=32.0)
    p.add_argument("--scroll-height", type=float, default=12.0)
    p.add_argument("--scroll-margin-x", type=float, default=14.0)
    p.add_argument("--scroll-margin-top", type=float, default=8.0)
    p.add_argument("--px-per-mm", type=float, default=3.0)
    p.add_argument("--columns", type=int, default=4)
    return p


def render_style(args: argparse.Namespace, style: str) -> Image.Image:
    nx = max(1, int(round(args.plate_width * args.px_per_mm)))
    ny = max(1, int(round(args.plate_height * args.px_per_mm)))
    x_edges = np.linspace(-args.plate_width / 2.0, args.plate_width / 2.0, nx + 1)
    y_edges = np.linspace(-args.plate_height / 2.0, args.plate_height / 2.0, ny + 1)
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2.0
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2.0

    occupied = gen.rounded_rect_occupancy(x_centers, y_centers, args.plate_width, args.plate_height, args.corner_radius)
    font = gen.existing_font(args.font)
    text_layout = gen.render_text_layout(
        gen.normalize_text(args.text),
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
    text_mask = gen.image_mask_to_model_mask(text_layout.mask) & occupied
    scroll_mask = gen.make_top_scroll_mask(
        x_centers,
        y_centers,
        args.plate_width,
        args.plate_height,
        args.scroll_width,
        args.scroll_height,
        args.scroll_margin_x,
        args.scroll_margin_top,
        style,
    ) & occupied

    image = Image.new("RGB", (nx, ny), (238, 238, 232))
    pixels = np.asarray(image).copy()
    display_plate = np.flipud(occupied)
    display_text = np.flipud(text_mask | scroll_mask)
    pixels[display_plate] = (86, 116, 76)
    pixels[display_text] = (246, 238, 196)
    return Image.fromarray(pixels)


def label_image(image: Image.Image, index: int) -> Image.Image:
    pad = 24
    labeled = Image.new("RGB", (image.width, image.height + pad), (238, 238, 232))
    labeled.paste(image, (0, pad))
    draw = ImageDraw.Draw(labeled)
    font = ImageFont.load_default()
    draw.text((8, 6), f"{index:02d}", fill=(32, 32, 32), font=font)
    return labeled


def make_contact_sheet(images: list[Image.Image], columns: int) -> Image.Image:
    columns = max(1, columns)
    rows = int(math.ceil(len(images) / columns))
    gap = 16
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    sheet = Image.new("RGB", (columns * cell_w + (columns - 1) * gap, rows * cell_h + (rows - 1) * gap), (220, 220, 214))
    for index, image in enumerate(images):
        row, col = divmod(index, columns)
        x = col * (cell_w + gap)
        y = row * (cell_h + gap)
        sheet.paste(image, (x, y))
    return sheet


def main() -> None:
    args = parser().parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    previews = []
    for index, style in enumerate(gen.SCROLL_STYLES, start=1):
        preview = label_image(render_style(args, style), index)
        path = os.path.join(args.outdir, f"{index:02d}.png")
        preview.save(path)
        previews.append(preview)
        print(path)

    sheet_path = os.path.join(args.outdir, "all_scroll_styles.png")
    make_contact_sheet(previews, args.columns).save(sheet_path)
    print(sheet_path)


if __name__ == "__main__":
    main()
