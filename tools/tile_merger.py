
from PIL import Image
import argparse


def get_tile_rect(index, tiles_per_row, tile_size):
    tx = index % tiles_per_row
    ty = index // tiles_per_row
    x0 = tx * tile_size
    y0 = ty * tile_size
    return (x0, y0, x0 + tile_size, y0 + tile_size)


def copy_tiles(base_img, src_img, tile_indices, tile_size):
    base = base_img.copy()

    tiles_per_row = base.width // tile_size

    for idx in tile_indices:
        rect = get_tile_rect(idx, tiles_per_row, tile_size)
        tile = src_img.crop(rect)
        base.paste(tile, rect)

    return base


def parse_range(rng_str):
    result = set()

    parts = rng_str.split(',')
    for part in parts:
        if '-' in part:
            a, b = part.split('-')
            result.update(range(int(a,0x10), int(b,0x10) + 1))
        else:
            result.add(int(part,0x10))

    return sorted(result)


def main():
    parser = argparse.ArgumentParser(description="Tile sheet merger")
    parser.add_argument("base", help="Base tile sheet (destination)")
    parser.add_argument("source", help="Source tile sheet")
    parser.add_argument("output", help="Output tile sheet")
    parser.add_argument("--tiles", required=True,
                        help="Tile indices (e.g. 0-10,32,40-50, in hexadecimal)")
    parser.add_argument("--tile-size", type=int, default=16,
                        help="Tile size (default: 16)")

    args = parser.parse_args()

    base_img = Image.open(args.base)
    src_img = Image.open(args.source)

    if base_img.size != src_img.size:
        raise ValueError("Images must have the same dimensions")

    if (base_img.width % args.tile_size != 0 or
        base_img.height % args.tile_size != 0):
        raise ValueError("Image dimensions must be multiples of tile size")

    tile_indices = parse_range(args.tiles)

    # Optional safety check
    tiles_per_row = base_img.width // args.tile_size
    tiles_per_col = base_img.height // args.tile_size
    max_tiles = tiles_per_row * tiles_per_col

    if any(i >= max_tiles for i in tile_indices):
        raise ValueError("Tile index out of range")

    result = copy_tiles(base_img, src_img, tile_indices, args.tile_size)

    result.save(args.output)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()