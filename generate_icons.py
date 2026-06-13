"""Generate PWA icons (192x192, 512x512) with no external dependencies.

Draws a dark background, a purple level-ring circle, and a white "7"
in the center, then writes raw PNG bytes via zlib.
"""
import math
import struct
import zlib

BG = (10, 10, 11)       # #0a0a0b
PURPLE = (127, 119, 221)  # #7F77DD
WHITE = (232, 232, 236)   # #e8e8ec

FONT_7 = [
    "11111",
    "00001",
    "00010",
    "00100",
    "01000",
    "01000",
    "01000",
]


def make_icon(size, path):
    pixels = [[BG] * size for _ in range(size)]

    cx = cy = size / 2
    r_outer = size * 0.42
    thickness = size * 0.07

    for y in range(size):
        for x in range(size):
            dx, dy = x - cx + 0.5, y - cy + 0.5
            dist = math.sqrt(dx * dx + dy * dy)
            if r_outer - thickness <= dist <= r_outer:
                pixels[y][x] = PURPLE

    rows, cols = len(FONT_7), len(FONT_7[0])
    scale = size // 16
    fw, fh = cols * scale, rows * scale
    ox, oy = (size - fw) // 2, (size - fh) // 2

    for ry, row in enumerate(FONT_7):
        for rx, ch in enumerate(row):
            if ch == "1":
                for sy in range(scale):
                    for sx in range(scale):
                        px, py = ox + rx * scale + sx, oy + ry * scale + sy
                        if 0 <= px < size and 0 <= py < size:
                            pixels[py][px] = WHITE

    write_png(path, pixels, size, size)


def write_png(path, pixels, width, height):
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for (r, g, b) in row:
            raw.extend((r, g, b))

    compressed = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", compressed))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    make_icon(192, "icon-192.png")
    make_icon(512, "icon-512.png")
    print("Generated icon-192.png and icon-512.png")
