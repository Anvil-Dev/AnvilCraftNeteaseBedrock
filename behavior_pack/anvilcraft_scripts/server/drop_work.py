# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""在落点处理掉落物，扣料失败时退回已收原料，保留未能生成的物品。"""

from math import floor
from collections import Counter

from anvilcraft_scripts.common.drop_recipes import (
    CAULDRON, Drop, RECIPES, in_recipe_area, match_drops, products, usable_platform,
)


class DropDelivery(object):
    """把引擎暂时拒绝生成的余料、产物或退款保存在当前存档。"""

    KEY = "anvilcraft:pending_drops_v1"

    def __init__(self, system, factory, level, log):
        self._system = system
        self._factory = factory
        self._level = level
        self._log = log
        self._store = None
        self.pending = []
        self._dirty = False

    def load(self):
        if self._store is None:
            self._store = self._factory.CreateExtraData(self._level)
            self.pending = self._store.GetExtraData(self.KEY) or []
            # 旧 ID 的西瓜片需要先迁移，再补发并写回存档。
            for _, _, item in self.pending:
                if item.get("newItemName") == "minecraft:melon":
                    item["newItemName"] = "minecraft:melon_slice"
                    self._dirty = True

    def _save(self, records):
        saved = self._store.SetExtraData(self.KEY, records, True)
        if not saved:
            self._log.error("[AnvilCraft] could not save pending drops; count=%d", len(records))
        return saved

    def _spawn(self, row):
        dim, pos, item = row
        entity = self._system.CreateEngineItemEntity(item, dim, tuple(pos))
        return None if entity in (None, False, "", "-1", -1) else entity

    def send(self, dim, deliveries):
        for pos, item in deliveries:
            row = [dim, list(pos), item]
            if not self._spawn(row):
                self.pending.append(row)
                self._dirty = True
                self._log.warning("[AnvilCraft] deferred item dim=%s pos=%s count=%s",
                                  dim, pos, item["count"])
        self.flush()

    def flush(self):
        if self._dirty:
            self._dirty = not self._save(self.pending)
        return not self._dirty

    def retry(self):
        if not self.flush() or not self.pending:
            return
        chunks = self._factory.CreateChunkSource(self._level)
        for index, row in enumerate(self.pending):
            cell = tuple(int(floor(value)) for value in row[1])
            if chunks.CheckChunkState(row[0], cell):
                break
        else:
            return
        # 保留原凭据直到发放和提交都成功。存档不可写时暂缓创建实体。
        if not self._save(self.pending):
            return
        entity = self._spawn(row)
        if entity is None:
            return
        rest = self.pending[:index] + self.pending[index + 1:]
        if self._save(rest):
            self.pending = rest
            return
        if not self._system.DestroyEntity(entity):
            # 产物已生成且无法撤回，只重试保存，避免在本次会话重复发放。
            self.pending = rest
            self._dirty = True
            self._log.error("[AnvilCraft] spawned item could not be retracted id=%s record=%r",
                            entity, row)


class DropWork(object):
    """只读取落点所在维度的掉落物，并在同一服务端回调内完成一批加工。"""

    def __init__(self, api, system, log):
        self._factory = api.GetEngineCompFactory()
        self._level = api.GetLevelId()
        self._system = system
        self._log = log
        self._delivery = DropDelivery(system, self._factory, self._level, log)
        self._claimed = {}
        self._busy = set()

    def load(self):
        self._delivery.load()

    def close(self):
        self._delivery.flush()

    def tick(self, tick):
        for entity, deadline in self._claimed.items():
            if tick >= deadline:
                del self._claimed[entity]
        if tick % 30 == 0:
            self._delivery.retry()

    def _read(self, entity, platform, dim, pos):
        kind = self._factory.CreateEngineType(entity)
        if kind is None or kind.GetEngineTypeStr() != "minecraft:item":
            return None
        dimension = self._factory.CreateDimension(entity)
        if dimension is None or dimension.GetEntityDimensionId() != dim:
            return None
        position = self._factory.CreatePos(entity)
        feet = position.GetFootPos() if position is not None else None
        if feet is None or not in_recipe_area(platform, pos, feet):
            return None
        item = self._factory.CreateItem(self._level).GetDroppedItem(entity, True)
        if not item or item.get("count", 0) <= 0:
            return None
        return Drop(entity, tuple(feet), item)

    def _snapshot(self, platform, dim, pos):
        x, y, z = pos
        game = self._factory.CreateGame(self._level)
        ids = game.GetEntitiesInSquareArea(None, (x - 1, y, z - 1), (x + 2, y + 2, z + 2), dim)
        drops = []
        for entity in sorted(set(ids or ())):
            if entity not in self._claimed:
                drop = self._read(entity, platform, dim, pos)
                if drop is not None:
                    drops.append(drop)
        return drops

    def _valid_platform(self, platform, dim, pos):
        block = self._factory.CreateBlockInfo(self._level).GetBlockNew(pos, dim) or {}
        if block.get("name") != platform:
            return False
        states = self._factory.CreateBlockState(self._level).GetBlockStates(pos, dim) or {}
        return usable_platform(platform, states)

    def process(self, platform, dim, pos, tick):
        key = (dim, pos)
        if platform not in RECIPES or key in self._busy:
            return
        if not self._valid_platform(platform, dim, pos):
            return
        self.load()
        self._busy.add(key)
        try:
            batch = match_drops(platform, self._snapshot(platform, dim, pos))
            if batch and self._valid_platform(platform, dim, pos):
                self._exchange(platform, dim, pos, tick, batch)
        finally:
            self._busy.remove(key)

    def _exchange(self, platform, dim, pos, tick, batch):
        removed = []
        change = []
        for drop, take in batch.debits:
            current = self._read(drop.entity, platform, dim, pos)
            available = current and current.item == drop.item and drop.entity not in self._claimed
            if available:
                # 先认领，再调用可能同步触发其他事件的引擎接口。
                self._claimed[drop.entity] = tick + 2
                available = self._system.DestroyEntity(drop.entity)
                if not available:
                    del self._claimed[drop.entity]
            if not available:
                self._delivery.send(dim, removed)
                self._log.warning("[AnvilCraft] item exchange interrupted dim=%s pos=%s", dim, pos)
                return
            removed.append((current.pos, current.item))
            if take < current.item["count"]:
                rest = dict(current.item)
                rest["count"] -= take
                change.append((current.pos, rest))
        if not self._valid_platform(platform, dim, pos):
            self._delivery.send(dim, removed)
            return
        x, y, z = pos
        output_pos = (x + 0.5, y + (0.25 if platform == CAULDRON else 0), z + 0.5)
        output = list(products(batch))
        change.extend((output_pos, item) for item in output)
        self._delivery.send(dim, change)
        totals = Counter()
        for item in output:
            totals[item["newItemName"]] += item["count"]
        self._log.info("[AnvilCraft] item process dim=%s pos=%s recipe=%s batches=%d results=%s",
                       dim, pos, batch.recipe.source, batch.times, sorted(totals.items()))
