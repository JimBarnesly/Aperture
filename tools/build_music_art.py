#!/usr/bin/env python3
"""Deterministic original native turntable textures. No downloaded artwork."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def generate(output=None):
    output = Path(output or ROOT / 'skin/media/aperture/music')
    output.mkdir(parents=True, exist_ok=True)
    size = 1024
    platter = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(platter)
    draw.ellipse((12, 12, 1012, 1012), fill='#080b10', outline='#71808b', width=6)
    draw.ellipse((28, 28, 996, 996), fill='#202a33', outline='#3d4b55', width=18)
    for inset in range(56, 170, 9):
        draw.ellipse((inset, inset, size-inset, size-inset), outline=(69, 80, 90, 140), width=2)
    platter.save(output / 'platter.png', optimize=True)
    mask = Image.new('RGBA', (size, size))
    ImageDraw.Draw(mask).ellipse((2, 2, 1022, 1022), fill='white')
    mask.save(output / 'disc-mask.png', optimize=True)
    grooves = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(grooves)
    for inset in range(9, 460, 14):
        draw.ellipse((inset, inset, size-inset, size-inset), outline=(0, 0, 0, 36), width=2)
    draw.ellipse((435, 435, 589, 589), outline=(4, 8, 12, 190), width=16)
    draw.arc((9, 9, 1015, 1015), 205, 290, fill=(255, 255, 255, 65), width=5)
    grooves.save(output / 'grooves.png', optimize=True)
    spindle = Image.new('RGBA', (96, 96))
    draw = ImageDraw.Draw(spindle)
    draw.ellipse((1, 1, 95, 95), fill='#28343e', outline='#7d8d97', width=4)
    draw.ellipse((24, 24, 72, 72), fill='#9babb3', outline='#d3dce0', width=3)
    draw.ellipse((33, 29, 54, 50), fill='#ecf2f3')
    spindle.save(output / 'spindle.png', optimize=True)
    # Original alpha mask for a short, fading floor reflection.
    reflection = Image.new('RGBA', (16, 440))
    draw = ImageDraw.Draw(reflection)
    for y in range(440):
        alpha = round(255 * max(0, 1 - y / 160) ** 1.8)
        draw.line((0, 439-y, 15, 439-y), fill=(255, 255, 255, alpha))
    reflection.save(output / 'reflection-fade.png', optimize=True)


if __name__ == '__main__':
    generate()
