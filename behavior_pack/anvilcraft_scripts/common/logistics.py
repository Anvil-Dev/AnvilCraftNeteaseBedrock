# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""物流方块、输入区域与六个输出方向。"""

CHUTE = "anvilcraft:chute"
CHUTE_DOWN = "anvilcraft:chute_down"
SIMPLE_CHUTE = "anvilcraft:simple_chute"
SIMPLE_DOWN = "anvilcraft:simple_chute_down"
SIMPLE_TALL = "anvilcraft:simple_chute_tall"
SIMPLE_TALL_DOWN = "anvilcraft:simple_chute_tall_down"
CHUTES = (CHUTE, CHUTE_DOWN)
SIMPLE_CHUTES = (SIMPLE_CHUTE, SIMPLE_DOWN, SIMPLE_TALL, SIMPLE_TALL_DOWN)
ORDINARY_CHUTES = CHUTES + SIMPLE_CHUTES
DOWN_CHUTES = (CHUTE_DOWN, SIMPLE_DOWN, SIMPLE_TALL_DOWN)
MAGNETIC_CHUTE = "anvilcraft:magnetic_chute"
LOGISTICS = ORDINARY_CHUTES + (MAGNETIC_CHUTE,)
COLLECTION_AREA = "anvilcraft:collection_area"
COOLDOWN_KEY = "anvilcraft:chute_cooldown"
DIRECTIONS = ((0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0))
CHUTE_BOXES = {
    CHUTE: (((2, 8, 2), (14, 12, 14)), ((4, 4, 0), (12, 12, 12)), ((0, 12, 0), (16, 16, 16))),
    CHUTE_DOWN: (((0, 12, 0), (16, 16, 16)), ((2, 0, 2), (14, 12, 14))),
    SIMPLE_CHUTE: (((4, 4, 0), (12, 12, 12)),),
    SIMPLE_DOWN: (((2, 0, 2), (14, 12, 14)),),
    SIMPLE_TALL: (((4, 4, 0), (12, 12, 12)), ((2, 8, 2), (14, 16, 14))),
    SIMPLE_TALL_DOWN: (((2, 0, 2), (14, 16, 14)),),
}
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

    if name in ORDINARY_CHUTES:
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


def chute_form(name, facing, neighbours):
    """根据指向本格的出口选择普通、简易及高接头形态，保留既有简易溜槽的方向。"""
    incoming = [side for side, (other, direction) in enumerate(neighbours)
                if other in LOGISTICS and direction == side ^ 1]
    if name in CHUTES:
        for side in incoming:
            if side == 0 and facing == 0:
                return None
            if side >= 2:
                if facing == side:
                    facing ^= 1
                other, direction = neighbours[facing]
                if other in LOGISTICS and direction == facing ^ 1:
                    return None
    if not incoming:
        return (CHUTE_DOWN if facing == 0 else CHUTE), facing
    tall = 1 in incoming and neighbours[1][0] != MAGNETIC_CHUTE
    if facing == 0:
        return (SIMPLE_TALL_DOWN if tall else SIMPLE_DOWN), 0
    return (SIMPLE_TALL if tall else SIMPLE_CHUTE), facing


def touches_chute(name, facing, pos, feet):
    """只收集与原版槽体碰撞盒相交的掉落物，避免从管道旁边的空隙吸入。"""
    x, y, z = (16 * (feet[i] - pos[i]) for i in range(3))
    if name not in DOWN_CHUTES:
        if facing == 3:
            x, z = 16 - x, 16 - z
        elif facing == 4:
            x, z = 16 - z, x
        elif facing == 5:
            x, z = z, 16 - x
    return any(x + 2 > low[0] and x - 2 < high[0]
               and y + 4 > low[1] and y < high[1]
               and z + 2 > low[2] and z - 2 < high[2]
               for low, high in CHUTE_BOXES[name])
