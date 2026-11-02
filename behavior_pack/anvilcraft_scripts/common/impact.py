# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""将一次下落与一次方块粉碎配对，只在还原为方块时结算。"""

CRUSH_RESULTS = {
    "minecraft:cobblestone": "minecraft:gravel",
    "minecraft:gravel": "minecraft:sand",
    "minecraft:polished_andesite": "minecraft:andesite",
    "minecraft:polished_diorite": "minecraft:diorite",
    "minecraft:polished_granite": "minecraft:granite",
    "minecraft:granite": "minecraft:red_sand",
    "minecraft:soul_soil": "minecraft:soul_sand",
    "minecraft:stone_bricks": "minecraft:cracked_stone_bricks",
    "minecraft:nether_brick": "minecraft:cracked_nether_bricks",
    "minecraft:polished_blackstone_bricks": "minecraft:cracked_polished_blackstone_bricks",
    "minecraft:deepslate_bricks": "minecraft:cracked_deepslate_bricks",
    "minecraft:deepslate_tiles": "minecraft:cracked_deepslate_tiles",
}
VANILLA_ANVILS = frozenset(("minecraft:anvil", "minecraft:chipped_anvil",
                            "minecraft:damaged_anvil"))


class FallingAnvils(object):
    """下落实体的记录仅在当前维度、当前存档有效。"""

    def __init__(self):
        self._starts = {}

    def start(self, dimension, entity, name, pos, tick):
        # 文档中开始事件的 ID 为 str，落地事件的同一 ID 为 int。
        self._starts.setdefault((dimension, str(entity)), (name, pos, tick))

    def land(self, dimension, entity, name, pos):
        entry = self._starts.pop((dimension, str(entity)), None)
        if entry is None or entry[1][1] <= pos[1]:
            return None
        if entry[0] != name and not (entry[0] in VANILLA_ANVILS and name in VANILLA_ANVILS):
            return None
        return (pos[0], pos[1] - 1, pos[2])

    def discard(self, dimension, entity):
        self._starts.pop((dimension, str(entity)), None)

    def unload(self, dimension, chunk_x, chunk_z, entities):
        for entity in entities:
            self.discard(dimension, entity)
        for key, (_, pos, _) in self._starts.items():
            if key[0] == dimension and (pos[0] // 16, pos[2] // 16) == (chunk_x, chunk_z):
                del self._starts[key]

    def expire(self, before_tick):
        for key, (_, _, tick) in self._starts.items():
            if tick <= before_tick:
                del self._starts[key]


def crush_at(blocks, dimension, pos, expected=None):
    """只替换上游配方明确列出的普通方块，保留容器和未加载的位置。"""
    current = blocks.GetBlockNew(pos, dimension)
    name = current.get("name") if current else None
    if expected is not None and name != expected:
        return None
    result = CRUSH_RESULTS.get(name)
    if result and blocks.SetBlockNew(pos, {"name": result, "aux": 0}, 0, dimension, True):
        return result
    return None
