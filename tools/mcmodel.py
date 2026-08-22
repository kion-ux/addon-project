"""Bedrock geometry builder with automatic box-UV packing.

The packer records, for every cube, the pixel rectangle of each of its six
faces.  `mctexture.py` consumes that map so generated textures always line up
with the generated UVs.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

FACES = ("up", "down", "east", "north", "west", "south")


class Cube:
    def __init__(
        self,
        origin: Sequence[float],
        size: Sequence[float],
        style: str = "base",
        inflate: float = 0.0,
        pivot: Optional[Sequence[float]] = None,
        rotation: Optional[Sequence[float]] = None,
        mirror: bool = False,
        decals: Optional[Dict[str, str]] = None,
        fixed_uv: Optional[Sequence[int]] = None,
    ):
        self.origin = [float(v) for v in origin]
        self.size = [float(v) for v in size]
        self.style = style
        self.inflate = inflate
        self.pivot = list(pivot) if pivot else None
        self.rotation = list(rotation) if rotation else None
        self.mirror = mirror
        # face -> decal name, e.g. {"north": "eyes_red"}
        self.decals = dict(decals or {})
        self.uv: Optional[List[int]] = None
        self.fixed = fixed_uv is not None
        self.rects: Dict[str, Tuple[int, int, int, int]] = {}
        if fixed_uv is not None:
            self.assign_uv(int(fixed_uv[0]), int(fixed_uv[1]))

    # texture footprint of a box-UV unwrap
    def uv_extent(self) -> Tuple[int, int]:
        sx, sy, sz = (max(1, int(round(v))) for v in self.size)
        return (2 * sx + 2 * sz, sy + sz)

    def assign_uv(self, u: int, v: int) -> None:
        self.uv = [u, v]
        sx, sy, sz = (max(1, int(round(val))) for val in self.size)
        self.rects = {
            "up": (u + sz, v, sx, sz),
            "down": (u + sz + sx, v, sx, sz),
            "east": (u, v + sz, sz, sy),
            "north": (u + sz, v + sz, sx, sy),
            "west": (u + sz + sx, v + sz, sz, sy),
            "south": (u + sz + sx + sz, v + sz, sx, sy),
        }

    def to_json(self) -> dict:
        out: dict = {"origin": self.origin, "size": self.size, "uv": self.uv}
        if self.inflate:
            out["inflate"] = self.inflate
        if self.mirror:
            out["mirror"] = True
        if self.rotation:
            out["pivot"] = self.pivot or [
                self.origin[0] + self.size[0] / 2,
                self.origin[1] + self.size[1] / 2,
                self.origin[2] + self.size[2] / 2,
            ]
            out["rotation"] = self.rotation
        return out


class Bone:
    def __init__(
        self,
        name: str,
        pivot: Sequence[float] = (0, 0, 0),
        parent: Optional[str] = None,
        rotation: Optional[Sequence[float]] = None,
        cubes: Optional[List[Cube]] = None,
        mirror: bool = False,
    ):
        self.name = name
        self.pivot = [float(v) for v in pivot]
        self.parent = parent
        self.rotation = list(rotation) if rotation else None
        self.cubes = list(cubes or [])
        self.mirror = mirror

    def add(self, cube: Cube) -> Cube:
        self.cubes.append(cube)
        return cube

    def to_json(self) -> dict:
        out: dict = {"name": self.name, "pivot": self.pivot}
        if self.parent:
            out["parent"] = self.parent
        if self.rotation:
            out["rotation"] = self.rotation
        if self.mirror:
            out["mirror"] = True
        if self.cubes:
            out["cubes"] = [c.to_json() for c in self.cubes]
        return out


class Model:
    def __init__(
        self,
        identifier: str,
        tex_w: int = 128,
        tex_h: int = 128,
        visible_bounds: Tuple[float, float, float] = (4, 4, 4),
        vb_offset: Tuple[float, float, float] = (0, 1.5, 0),
    ):
        self.identifier = identifier
        self.tex_w = tex_w
        self.tex_h = tex_h
        self.visible_bounds = visible_bounds
        self.vb_offset = vb_offset
        self.bones: List[Bone] = []

    def bone(self, name: str, pivot=(0, 0, 0), parent=None, rotation=None, mirror=False) -> Bone:
        b = Bone(name, pivot, parent, rotation, mirror=mirror)
        self.bones.append(b)
        return b

    def all_cubes(self) -> List[Cube]:
        return [c for b in self.bones for c in b.cubes]

    # --- shelf packer -------------------------------------------------
    def pack(self, padding: int = 1) -> None:
        cubes = sorted(
            [c for c in self.all_cubes() if not c.fixed],
            key=lambda c: (-c.uv_extent()[1], -c.uv_extent()[0]),
        )
        shelf_y = 0
        shelf_h = 0
        x = 0
        for cube in cubes:
            w, h = cube.uv_extent()
            if x + w > self.tex_w:
                shelf_y += shelf_h + padding
                shelf_h = 0
                x = 0
            if shelf_y + h > self.tex_h:
                raise ValueError(
                    f"{self.identifier}: texture {self.tex_w}x{self.tex_h} too small "
                    f"(needed row at y={shelf_y} for {h}px)"
                )
            cube.assign_uv(x, shelf_y)
            x += w + padding
            shelf_h = max(shelf_h, h)
        self.used_height = shelf_y + shelf_h

    def to_json(self) -> dict:
        return {
            "description": {
                "identifier": self.identifier,
                "texture_width": self.tex_w,
                "texture_height": self.tex_h,
                "visible_bounds_width": self.visible_bounds[0],
                "visible_bounds_height": self.visible_bounds[1],
                "visible_bounds_offset": list(self.vb_offset),
            },
            "bones": [b.to_json() for b in self.bones],
        }

    def write(self, path: str, shrink: bool = True) -> None:
        self.pack()
        if shrink:
            need = max(16, getattr(self, "used_height", self.tex_h))
            h = 16
            while h < need:
                h *= 2
            self.tex_h = min(self.tex_h, h)
        doc = {"format_version": "1.12.0", "minecraft:geometry": [self.to_json()]}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
