"""Reduce PNG images to an indexed palette (<= 256 colours) and optionally
upscale them pixel-wise (x2, x3...). Files are overwritten in place.

Usage:
    pngreduce.py [-s {1,2,3,4}] [-c N] [--dither] [-n] image.png [image2.png ...]
"""
import argparse
import sys
from PIL import Image


def exact_palette(img, max_colors):
    """If the image already has <= max_colors distinct colours, build a
    lossless indexed version. Returns None if there are too many colours."""
    rgba = img.convert("RGBA")
    colors = rgba.getcolors(max_colors)        # None if more than max_colors
    if colors is None:
        return None

    # most used colours first (cosmetic only)
    colors.sort(key=lambda c: -c[0])
    index = {rgba_val: i for i, (_, rgba_val) in enumerate(colors)}

    out = Image.new("P", rgba.size)
    raw = rgba.tobytes()   # RGBARGBA... (portable across Pillow versions)
    out.frombytes(bytes(index[tuple(raw[i:i + 4])]
                        for i in range(0, len(raw), 4)))

    palette = []
    alphas = []
    for _, (r, g, b, a) in colors:
        palette += [r, g, b]
        alphas.append(a)
    out.putpalette(palette)

    if any(a < 255 for a in alphas):
        out.info["transparency"] = bytes(alphas)
    return out


def quantize(img, max_colors, dither):
    """Lossy reduction when the image has more than max_colors colours."""
    d = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    if has_alpha:
        # FASTOCTREE is the only method that handles RGBA
        return img.convert("RGBA").quantize(
            max_colors, method=Image.Quantize.FASTOCTREE, dither=d)
    return img.convert("RGB").quantize(
        max_colors, method=Image.Quantize.MEDIANCUT, dither=d)


def process(path, scale, max_colors, dither, dry_run):
    with Image.open(path) as src:
        src.load()
        orig_mode, orig_size = src.mode, src.size

        out = exact_palette(src, max_colors)
        lossless = out is not None
        if out is None:
            out = quantize(src, max_colors, dither)

    if scale > 1:
        info = out.info.copy()
        out = out.resize((out.width * scale, out.height * scale),
                         Image.Resampling.NEAREST)
        out.info.update(info)      # keep the transparency entry

    ncols = len(out.getcolors(256) or [])
    print(f"{path}: {orig_mode} {orig_size[0]}x{orig_size[1]} -> "
          f"P {out.width}x{out.height}, {ncols} colours"
          f"{'' if lossless else ' (quantized, lossy)'}")

    if not dry_run:
        save_kw = {"optimize": True}
        if "transparency" in out.info:
            save_kw["transparency"] = out.info["transparency"]
        out.save(path, format="PNG", **save_kw)


def main():
    ap = argparse.ArgumentParser(
        description="Reduce PNGs to <=256 colours and scale pixel-wise "
                    "(overwrites the files).")
    ap.add_argument("files", nargs="+", help="PNG files to process")
    ap.add_argument("-s", "--scale", type=int, default=1,
                    help="integer pixel scale factor (1 = none, 2, 3...)")
    ap.add_argument("-c", "--colors", type=int, default=256,
                    help="maximum number of colours (default 256)")
    ap.add_argument("--dither", action="store_true",
                    help="use Floyd-Steinberg dithering when quantizing "
                         "(default: none)")
    ap.add_argument("-n", "--dry-run", action="store_true",
                    help="show what would be done without writing")
    args = ap.parse_args()

    if args.scale < 1:
        ap.error("scale must be >= 1")
    if not 2 <= args.colors <= 256:
        ap.error("colors must be between 2 and 256")

    errors = 0
    for f in args.files:
        try:
            process(f, args.scale, args.colors, args.dither, args.dry_run)
        except Exception as e:
            print(f"{f}: ERROR {e}", file=sys.stderr)
            errors += 1
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
