#!/usr/bin/env python3
"""Export visible layers from a simple Aseprite file as full-canvas PNGs.

This intentionally avoids external dependencies so the asset pipeline works on
machines that do not have the Aseprite CLI or Pillow installed.
"""

from __future__ import annotations

import argparse
import re
import struct
import zlib
from pathlib import Path


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, rgba: bytearray) -> None:
    raw = bytearray()
    row_len = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * row_len : (y + 1) * row_len])
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(payload)


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def u8(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def u16(self) -> int:
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def i16(self) -> int:
        value = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return value

    def u32(self) -> int:
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def skip(self, n: int) -> None:
        self.pos += n

    def string(self) -> str:
        length = self.u16()
        value = self.data[self.pos : self.pos + length].decode("utf-8", "replace")
        self.pos += length
        return value


def alpha_blend(dst: bytearray, width: int, height: int, src: bytes, sx: int, sy: int, sw: int, sh: int, opacity: int) -> None:
    if opacity <= 0:
        return
    for y in range(sh):
        dy = sy + y
        if dy < 0 or dy >= height:
            continue
        for x in range(sw):
            dx = sx + x
            if dx < 0 or dx >= width:
                continue
            si = (y * sw + x) * 4
            sr, sg, sb, sa = src[si], src[si + 1], src[si + 2], src[si + 3]
            sa = sa * opacity // 255
            if sa <= 0:
                continue
            di = (dy * width + dx) * 4
            dr, dg, db, da = dst[di], dst[di + 1], dst[di + 2], dst[di + 3]
            inv = 255 - sa
            out_a = sa + da * inv // 255
            if out_a <= 0:
                dst[di : di + 4] = b"\0\0\0\0"
                continue
            dst[di] = (sr * sa + dr * da * inv // 255) // out_a
            dst[di + 1] = (sg * sa + dg * da * inv // 255) // out_a
            dst[di + 2] = (sb * sa + db * da * inv // 255) // out_a
            dst[di + 3] = out_a


def sanitize(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return value or "layer"


def parse_aseprite(path: Path):
    r = Reader(path.read_bytes())
    file_size = r.u32()
    magic = r.u16()
    if magic != 0xA5E0:
        raise ValueError(f"{path} is not an Aseprite file")
    frames = r.u16()
    width = r.u16()
    height = r.u16()
    depth = r.u16()
    if depth != 32:
        raise ValueError(f"Only 32-bit RGBA Aseprite files are supported; got {depth}-bit")
    r.skip(4)  # flags
    r.skip(2)  # legacy speed
    r.skip(8)  # reserved zeroes
    r.skip(1)  # transparent palette index
    r.skip(3)
    r.skip(2)  # color count
    r.skip(2)  # pixel width/height
    r.skip(8)  # grid
    r.skip(84)

    layers: list[dict] = []
    cels: list[dict] = []
    for frame in range(frames):
        frame_start = r.pos
        frame_size = r.u32()
        frame_magic = r.u16()
        if frame_magic != 0xF1FA:
            raise ValueError(f"Unexpected frame magic 0x{frame_magic:04x}")
        old_chunks = r.u16()
        duration_ms = r.u16()
        r.skip(2)
        new_chunks = r.u32()
        chunk_count = new_chunks or old_chunks
        frame_end = frame_start + frame_size
        for _ in range(chunk_count):
            chunk_start = r.pos
            chunk_size = r.u32()
            chunk_type = r.u16()
            chunk_end = chunk_start + chunk_size
            if chunk_type == 0x2004:
                flags = r.u16()
                layer_type = r.u16()
                child_level = r.u16()
                r.skip(4)  # default layer width/height
                blend_mode = r.u16()
                opacity = r.u8()
                r.skip(3)
                layers.append(
                    {
                        "index": len(layers),
                        "name": r.string(),
                        "visible": bool(flags & 1),
                        "flags": flags,
                        "type": layer_type,
                        "childLevel": child_level,
                        "blendMode": blend_mode,
                        "opacity": opacity,
                    }
                )
            elif chunk_type == 0x2005:
                layer_index = r.u16()
                x = r.i16()
                y = r.i16()
                cel_opacity = r.u8()
                cel_type = r.u16()
                z_index = r.i16()
                r.skip(5)
                if cel_type in (0, 2):
                    cel_w = r.u16()
                    cel_h = r.u16()
                    if cel_type == 0:
                        pixels = r.data[r.pos : r.pos + cel_w * cel_h * 4]
                        r.skip(cel_w * cel_h * 4)
                    else:
                        pixels = zlib.decompress(r.data[r.pos : chunk_end])
                        r.pos = chunk_end
                    cels.append(
                        {
                            "frame": frame,
                            "layer": layer_index,
                            "x": x,
                            "y": y,
                            "opacity": cel_opacity,
                            "z": z_index,
                            "w": cel_w,
                            "h": cel_h,
                            "pixels": pixels,
                        }
                    )
                elif cel_type == 3:
                    r.skip(2)
            r.pos = chunk_end
        r.pos = frame_end
    if r.pos > file_size:
        raise ValueError("Read past declared Aseprite file size")
    return width, height, layers, cels


def export_layers(source: Path, out_dir: Path) -> None:
    width, height, layers, cels = parse_aseprite(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()

    layer_images = [bytearray(width * height * 4) for _ in layers]
    for cel in cels:
        if cel["frame"] != 0 or cel["layer"] >= len(layer_images):
            continue
        layer = layers[cel["layer"]]
        opacity = cel["opacity"] * layer["opacity"] // 255
        alpha_blend(layer_images[cel["layer"]], width, height, cel["pixels"], cel["x"], cel["y"], cel["w"], cel["h"], opacity)

    composite = bytearray(width * height * 4)
    manifest_lines = [
        f"source={source.name}",
        f"canvas={width}x{height}",
        "order=bottom-to-top",
        "",
    ]
    for layer in layers:
        if not layer["visible"]:
            continue
        pixels = layer_images[layer["index"]]
        if not any(pixels[i + 3] for i in range(0, len(pixels), 4)):
            continue
        filename = f"{layer['index']:02d}-{sanitize(layer['name'])}.png"
        write_png(out_dir / filename, width, height, pixels)
        alpha_blend(composite, width, height, pixels, 0, 0, width, height, 255)
        manifest_lines.append(f"{filename}\t{layer['name']}")

    write_png(out_dir / "_composite.png", width, height, composite)
    (out_dir / "manifest.txt").write_text("\n".join(manifest_lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    export_layers(args.source, args.out_dir)


if __name__ == "__main__":
    main()
