"""Bedrock geometry builder.

Two things this gives us that a hand-written .geo.json does not:

* **per-face UV with a texel scale** — a cube 4 units wide can own a 12-texel-wide
  patch of the atlas, so small parts (faces, insignia, blade edges) stay crisp
  instead of being limited to one texel per model unit.
* **an automatic packer that records every face rectangle**, which `mctexture.py`
  then paints into.  Model and texture can never drift apart.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

FACES = ("up", "down", "east", "north", "west", "south")

# candidate atlas sizes, tried in order until the parts fit
ATLAS_SIZES = [(128, 128), (256, 128), (256, 256), (512, 256), (512, 512),
               (1024, 512), (1024, 1024), (1024, 2048), (2048, 2048)]


class Cube:
    def __init__(
        self,
        origin: Sequence[float],
        size: Sequence[float],
        style: str = "base",
        inflate: float = 0.0,
        pivot: Optional[Sequence[float]] = None,
        rotation: Optional[Sequence[float]] = None,
        decals: Optional[Dict[str, str]] = None,
        uv_scale: Optional[int] = None,
        fixed_uv: Optional[Sequence[int]] = None,
        box_uv: bool = False,
    ):
        self.origin = [round(float(v), 3) for v in origin]
        self.size = [round(float(v), 3) for v in size]
        self.style = style
        self.inflate = inflate
        self.pivot = list(pivot) if pivot else None
        self.rotation = list(rotation) if rotation else None
        self.decals = dict(decals or {})
        self.uv_scale = uv_scale          # None -> inherit the model default
        self.box_uv = box_uv              # legacy box unwrap (vanilla armour layers)
        self.uv: Optional[List[int]] = None
        self.fixed = fixed_uv is not None
        self.rects: Dict[str, Tuple[int, int, int, int]] = {}
        self._scale = uv_scale or 1
        if fixed_uv is not None:
            self.assign_uv(int(fixed_uv[0]), int(fixed_uv[1]))

    # -- geometry of the unwrap ------------------------------------------
    def dims(self) -> Tuple[int, int, int]:
        s = self._scale
        return (max(1, int(round(self.size[0] * s))),
                max(1, int(round(self.size[1] * s))),
                max(1, int(round(self.size[2] * s))))

    def uv_extent(self) -> Tuple[int, int]:
        sx, sy, sz = self.dims()
        return (2 * sx + 2 * sz, sy + sz)

    def assign_uv(self, u: int, v: int) -> None:
        self.uv = [u, v]
        sx, sy, sz = self.dims()
        self.rects = {
            "up": (u + sz, v, sx, sz),
            "down": (u + sz + sx, v, sx, sz),
            "east": (u, v + sz, sz, sy),
            "north": (u + sz, v + sz, sx, sy),
            "west": (u + sz + sx, v + sz, sz, sy),
            "south": (u + sz + sx + sz, v + sz, sx, sy),
        }

    def to_json(self) -> dict:
        out: dict = {"origin": self.origin, "size": self.size}
        if self.box_uv:
            out["uv"] = self.uv
        else:
            out["uv"] = {
                face: {"uv": [r[0], r[1]], "uv_size": [r[2], r[3]]}
                for face, r in ((f, self.rects[f]) for f in FACES)
            }
        if self.inflate:
            out["inflate"] = self.inflate
        if self.rotation:
            out["pivot"] = self.pivot or [
                round(self.origin[0] + self.size[0] / 2, 3),
                round(self.origin[1] + self.size[1] / 2, 3),
                round(self.origin[2] + self.size[2] / 2, 3),
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
        binding: Optional[str] = None,
    ):
        self.name = name
        self.pivot = [round(float(v), 3) for v in pivot]
        self.parent = parent
        self.rotation = list(rotation) if rotation else None
        self.cubes = list(cubes or [])
        self.binding = binding

    def add(self, *cubes: Cube) -> Cube:
        for c in cubes:
            self.cubes.append(c)
        return cubes[-1]

    def to_json(self) -> dict:
        out: dict = {"name": self.name, "pivot": self.pivot}
        if self.parent:
            out["parent"] = self.parent
        if self.rotation:
            out["rotation"] = self.rotation
        if self.binding:
            out["binding"] = self.binding
        if self.cubes:
            out["cubes"] = [c.to_json() for c in self.cubes]
        return out


class Model:
    def __init__(
        self,
        identifier: str,
        uv_scale: int = 2,
        visible_bounds: Tuple[float, float] = (4, 4),
        vb_offset: Tuple[float, float, float] = (0, 1.5, 0),
        max_atlas: Tuple[int, int] = (512, 512),
    ):
        self.identifier = identifier
        self.uv_scale = uv_scale
        self.visible_bounds = visible_bounds
        self.vb_offset = vb_offset
        self.max_atlas = max_atlas
        self.tex_w = 0
        self.tex_h = 0
        self.bones: List[Bone] = []

    def bone(self, name: str, pivot=(0, 0, 0), parent=None, rotation=None,
             binding=None) -> Bone:
        b = Bone(name, pivot, parent, rotation, binding=binding)
        self.bones.append(b)
        return b

    def all_cubes(self) -> List[Cube]:
        return [c for b in self.bones for c in b.cubes]

    # -- shelf packer ----------------------------------------------------
    def _try_pack(self, width: int, height: int, padding: int) -> bool:
        cubes = sorted(
            [c for c in self.all_cubes() if not c.fixed],
            key=lambda c: (-c.uv_extent()[1], -c.uv_extent()[0]),
        )
        shelf_y = 0
        shelf_h = 0
        x = 0
        for cube in cubes:
            w, h = cube.uv_extent()
            if w > width:
                return False
            if x + w > width:
                shelf_y += shelf_h + padding
                shelf_h = 0
                x = 0
            if shelf_y + h > height:
                return False
            cube.assign_uv(x, shelf_y)
            x += w + padding
            shelf_h = max(shelf_h, h)
        self.used_height = shelf_y + shelf_h
        return True

    def pack(self, padding: int = 1) -> None:
        for cube in self.all_cubes():
            if cube.uv_scale is None:
                cube._scale = self.uv_scale
                if not cube.fixed:
                    cube.uv = None
        for width, height in ATLAS_SIZES:
            if width > self.max_atlas[0] or height > self.max_atlas[1]:
                continue
            if self._try_pack(width, height, padding):
                self.tex_w, self.tex_h = width, height
                return
        raise ValueError(
            f"{self.identifier}: does not fit in {self.max_atlas} at uv_scale "
            f"{self.uv_scale} ({len(self.all_cubes())} cubes)"
        )

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

    def write(self, path: str) -> None:
        if not self.tex_w:
            self.pack()
        doc = {"format_version": "1.12.0", "minecraft:geometry": [self.to_json()]}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    def stats(self) -> str:
        return (f"{len(self.bones)} bones / {len(self.all_cubes())} cubes / "
                f"{self.tex_w}x{self.tex_h} @x{self.uv_scale}")
