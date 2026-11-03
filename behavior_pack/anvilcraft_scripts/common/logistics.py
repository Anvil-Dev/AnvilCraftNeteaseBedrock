# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""物流方块、输入区域与六个输出方向。"""

CHUTE = "anvilcraft:chute"
MAGNETIC_CHUTE = "anvilcraft:magnetic_chute"
LOGISTICS = (CHUTE, MAGNETIC_CHUTE)
COLLECTION_AREA = "anvilcraft:collection_area"
DIRECTIONS = ((0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0))
CONTAINERS = frozenset(("minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel",
                        "minecraft:hopper", "minecraft:dropper", "minecraft:dispenser",
                        "minecraft:undyed_shulker_box") + tuple("minecraft:" + colour + "_shulker_box" for colour in (
                            "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
                            "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")))


def offset(pos, direction):
    return tuple(pos[i] + direction[i] for i in range(3))


def placement_facing(name, face, sneaking, look, neighbours):
    """按 Java 放置规则选择输出面，入口两端相互对冲时返回 None 拒绝放置。"""
    def points(index, direction):
        block, facing = neighbours[index]
        return block in LOGISTICS and facing == direction

    if name == CHUTE:
        facing = face if sneaking else face ^ 1
        if facing < 2:
            facing = 0
        for side in range(6):
            if not points(side, side ^ 1):
                continue
            if side == 0 and facing == 0:
                return None
            if side >= 2:
                if facing == side:
                    facing ^= 1
                if points(facing, facing ^ 1):
                    return None
        return facing
    facing = max(range(6), key=lambda index: sum(look[i] * DIRECTIONS[index][i] for i in range(3)))
    if sneaking:
        facing ^= 1
    if neighbours[face ^ 1][0] == MAGNETIC_CHUTE and points(face ^ 1, face):
        facing = face
    if points(facing, facing ^ 1):
        facing ^= 1
    return None if points(facing ^ 1, facing) and points(facing, facing ^ 1) else facing
