# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""将一次下落与一次方块粉碎配对，只在还原为方块时结算。"""

CRUSH_RESULTS = {"minecraft:cobblestone": "minecraft:gravel",
                 "minecraft:gravel": "minecraft:sand"}


class FallingAnvils(object):
    """下落实体的记录仅在当前维度、当前存档有效。"""

    def __init__(self):
        self._starts = {}

    def start(self, dimension, entity, name, pos, tick):
        # 文档中开始事件的 ID 为 str，落地事件的同一 ID 为 int。
        self._starts.setdefault((dimension, str(entity)), (name, pos, tick))

    def land(self, dimension, entity, name, pos):
        entry = self._starts.pop((dimension, str(entity)), None)
        if entry is None or entry[0] != name or entry[1][1] <= pos[1]:
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


def crush_at(blocks, dimension, pos):
    """只替换两条上游配方明确列出的原料；区块未加载时不写入。"""
    current = blocks.GetBlockNew(pos, dimension)
    result = CRUSH_RESULTS.get(current.get("name")) if current else None
    if result and blocks.SetBlockNew(pos, {"name": result, "aux": 0}, 0, dimension, True):
        return result
    return None
