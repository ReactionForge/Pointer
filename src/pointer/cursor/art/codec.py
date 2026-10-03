"""Windows CUR/DIB and RIFF encoding."""
import struct
from pointer.paths import ASSET_ROOT
ROOT = ASSET_ROOT / "reference"

def dib(image):
    size = image.width
    pixels = image.tobytes("raw", "BGRA")
    stride = size * 4
    bottom_up = b"".join(pixels[y * stride:(y + 1) * stride] for y in range(size - 1, -1, -1))
    mask_stride = ((size + 31) // 32) * 4
    alpha = image.getchannel("A")
    rows = []
    for y in range(size - 1, -1, -1):
        row = bytearray(mask_stride)
        for x in range(size):
            if alpha.getpixel((x, y)) == 0:
                row[x // 8] |= 1 << (7 - x % 8)
        rows.append(bytes(row))
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(bottom_up), 0, 0, 0, 0)
    return header + bottom_up + b"".join(rows)


def cursor_bytes(images, hotspot):
    bodies = [dib(image) for image in images]
    offset = 6 + 16 * len(images)
    entries = []
    for image, body in zip(images, bodies):
        size = image.width
        dimension = size if size < 256 else 0
        x = round(hotspot[0] * size / 32)
        y = round(hotspot[1] * size / 32)
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, x, y, len(body), offset))
        offset += len(body)
    return struct.pack("<HHH", 0, 2, len(images)) + b"".join(entries) + b"".join(bodies)


def write_cursor(images, filename, hotspot):
    cursor = cursor_bytes(images, hotspot)
    (ROOT / filename).write_bytes(cursor)
    print(f"Created {ROOT / filename} ({len(cursor)} bytes, {len(images)} sizes)")


def riff_chunk(tag, content):
    return tag + struct.pack("<I", len(content)) + content + (b"\0" if len(content) % 2 else b"")

