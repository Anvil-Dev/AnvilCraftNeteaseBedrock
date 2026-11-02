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
                        "minecraft:undyed_shulker_box"))


def offset(pos, direction):
    return tuple(pos[i] + direction[i] for i in range(3))
