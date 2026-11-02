# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""处理四种加工台的投料、改装、收料与落砧加工。"""

from copy import deepcopy

from anvilcraft_scripts.common.drop_recipes import (
    ATTACHMENTS, TABLES, Drop, item_name, match_drops, products,
)
from anvilcraft_scripts.server.inventory import Inventories, insert


class Stations(object):
    """加工台只在加载的区块中运行，交互使用服务端手持物品与玩家位置。"""

    def __init__(self, api, system, log, drop_work):
        self._api, self._system, self._log = api, system, log
        self.factory, self.level = api.GetEngineCompFactory(), api.GetLevelId()
        self.inventory = Inventories(self.factory, self.level, log)
        self._drops = drop_work
        self.busy = set()
        self._used = {}
        self.tick = 0

    def _name(self, dim, pos):
        block = self.factory.CreateBlockInfo(self.level).GetBlockNew(pos, dim) or {}
        return block.get("name")

    def reachable(self, player, dim, pos):
        if not self.factory.CreateChunkSource(self.level).CheckChunkState(dim, pos):
            return False
        if self.factory.CreateDimension(player).GetEntityDimensionId() != dim:
            return False
        feet = self.factory.CreatePos(player).GetFootPos()
        return feet is not None and sum((feet[i] - pos[i] - 0.5) ** 2 for i in range(3)) <= 36

    def maximum(self, item):
        info = self.factory.CreateItem(self.level).GetItemBasicInfo(
            item_name(item), item.get("newAuxValue", item.get("auxValue", 0))) or {}
        return max(1, min(64, info.get("maxStackSize", 1)))

    def send(self, dim, pos, items):
        self._drops.deliver(dim, [(tuple(pos), item) for item in items])

    def _return_inventory(self, dim, pos):
        key = (dim, pos)
        if key in self.busy:
            return
        self.busy.add(key)
        try:
            self._return_inventory_locked(dim, pos)
        finally:
            self.busy.remove(key)

    def _return_inventory_locked(self, dim, pos):
        if self.inventory.get(dim, pos).get("transfer"):
            return
        self._restore_liquid(dim, pos)
        record = self.inventory.get(dim, pos)
        remaining = dict(record, items=[]) if record.get("liquid") else None
        if self.inventory.write(dim, pos, remaining):
            self.send(dim, (pos[0] + 0.5, pos[1] + 0.5, pos[2] + 0.5), record["items"])

    def _finish(self, dim, pos):
        self.busy.remove((dim, pos))
        loaded = self.factory.CreateChunkSource(self.level).CheckChunkState(dim, pos)
        if loaded and self._name(dim, pos) not in TABLES:
            self._return_inventory(dim, pos)

    def advance(self, tick):
        self.tick = tick
        if tick % 30:
            return
        chunks = self.factory.CreateChunkSource(self.level)
        for dim, pos, record in self.inventory.scan(16, "tables"):
            if record.get("logistics"):
                continue
            if (dim, pos) not in self.busy and chunks.CheckChunkState(dim, pos):
                if self._name(dim, pos) not in TABLES:
                    self._return_inventory(dim, pos)
                else:
                    self._restore_liquid(dim, pos)

    def _restore_liquid(self, dim, pos):
        record = self.inventory.get(dim, pos)
        liquid = record.get("liquid")
        if liquid:
            blocks = self.factory.CreateBlockInfo(self.level)
            current = blocks.GetLiquidBlock(pos, dim)
            block = blocks.GetBlockNew(pos, dim) or {}
            if block.get("name") == "minecraft:air":
                restored = blocks.SetBlockNew(pos, liquid, 0, dim)
            elif block.get("name") == liquid.get("name"):
                restored = True
            else:
                restored = current == liquid or (block.get("name") in TABLES and
                                                 blocks.SetLiquidBlock(pos, liquid, dim))
            if restored:
                del record["liquid"]
                self.inventory.write(dim, pos, record)

    def absorb(self, dim, pos, name):
        """先确认完整掉落物快照，接收失败时退回已取走的物品。"""
        for drop in self._drops.snapshot(name, dim, pos):
            record = self.inventory.get(dim, pos)
            if record.get("transfer"):
                return
            items, take = insert(record["items"], drop.item, 8, self.maximum(drop.item), True)
            if not take or self._name(dim, pos) != name:
                continue
            if not self._drops.take(drop, name, dim, pos, self.tick):
                continue
            record["items"] = items
            if self.inventory.write(dim, pos, record):
                if take < drop.item["count"]:
                    rest = deepcopy(drop.item)
                    rest["count"] -= take
                    self.send(dim, drop.pos, [rest])
            else:
                self.send(dim, drop.pos, [drop.item])

    def block_tick(self, args):
        name = args["blockName"]
        if name not in TABLES:
            return
        dim = args["dimension"]
        pos = (args["posX"], args["posY"], args["posZ"])
        key = (dim, pos)
        if key in self.busy or self._name(dim, pos) != name:
            return
        self.busy.add(key)
        try:
            self._restore_liquid(dim, pos)
            self.absorb(dim, pos, name)
        finally:
            self._finish(dim, pos)

    def process(self, name, dim, pos):
        key = (dim, pos)
        if key in self.busy or self._name(dim, pos) != name:
            return
        self.busy.add(key)
        try:
            self.absorb(dim, pos, name)
            record = self.inventory.get(dim, pos)
            if record.get("transfer"):
                return
            drops = [Drop(i, pos, item) for i, item in enumerate(record["items"])]
            batch = match_drops(name, drops)
            if batch is None or self._name(dim, pos) != name:
                return
            for drop, take in batch.debits:
                record["items"][drop.entity]["count"] -= take
            record["items"] = [item for item in record["items"] if item["count"] > 0]
            if self.inventory.write(dim, pos, record):
                x, y, z = pos
                self.send(dim, (x + 0.5, y, z + 0.5), list(products(batch)))
                self._log.info("[AnvilCraft] table process dim=%s pos=%s recipe=%s batches=%d",
                               dim, pos, batch.recipe.source, batch.times)
        finally:
            self._finish(dim, pos)

    def carried(self, player):
        kind = self._api.GetMinecraftEnum().ItemPosType.CARRIED
        return self.factory.CreateItem(player).GetPlayerItem(kind, 0, True)

    def replace_carried(self, player, old, take):
        if self.carried(player) != old:
            return False
        rest = deepcopy(old)
        rest["count"] -= take
        return self.factory.CreateItem(player).SpawnItemToPlayerCarried(rest, player)

    def _convert(self, player, dim, pos, name, item, target):
        if target == name:
            return
        blocks = self.factory.CreateBlockInfo(self.level)
        liquid = blocks.GetLiquidBlock(pos, dim)
        if liquid and liquid.get("name") != "minecraft:air":
            record = self.inventory.get(dim, pos)
            if record.get("transfer"):
                return
            record["liquid"] = liquid
            if not self.inventory.write(dim, pos, record):
                return
        if not self.replace_carried(player, item, 1):
            return
        unchanged = self._name(dim, pos) == name
        if unchanged:
            blocks.SetBlockNew(pos, {"name": target, "aux": 0}, 0, dim)
        if not unchanged or self._name(dim, pos) != target:
            refund = deepcopy(item)
            refund["count"] = 1
            self.send(dim, self.factory.CreatePos(player).GetFootPos(), [refund])
            return
        self._restore_liquid(dim, pos)
        if name in ATTACHMENTS:
            self.send(dim, self.factory.CreatePos(player).GetFootPos(), [
                {"newItemName": ATTACHMENTS[name], "newAuxValue": 0, "count": 1}])

    def use(self, args):
        if args["blockName"] not in TABLES:
            return
        args["cancel"] = True
        player, dim = args["playerId"], args["dimensionId"]
        pos = (args["x"], args["y"], args["z"])
        key = (dim, pos)
        face = args.get("face")
        if face not in (0, 1, 2, 3, 4, 5) or key in self.busy:
            return
        if self._used.get(player, -1) > self.tick or not self.reachable(player, dim, pos):
            return
        name = self._name(dim, pos)
        if name != args["blockName"]:
            return
        self._used[player] = self.tick + 8
        self.busy.add(key)
        try:
            record = self.inventory.get(dim, pos)
            if record.get("transfer"):
                return
            item = self.carried(player)
            if face != 1:
                target = next((table for table, material in ATTACHMENTS.items()
                               if item and item.get("count", 0) > 0 and item_name(item) == material), None)
                if target:
                    self._convert(player, dim, pos, name, item, target)
                return
            if item and item.get("count", 0) > 0:
                items, take = insert(record["items"], item, 8, self.maximum(item), True)
                if take and self.replace_carried(player, item, take):
                    record["items"] = items
                    if not self.inventory.write(dim, pos, record):
                        refund = deepcopy(item)
                        refund["count"] = take
                        self.send(dim, self.factory.CreatePos(player).GetFootPos(), [refund])
            elif record["items"]:
                items = record["items"]
                record["items"] = []
                if self.inventory.write(dim, pos, record):
                    self.send(dim, (pos[0] + 1.25, pos[1] + 0.5, pos[2] + 0.5), items)
        finally:
            self._finish(dim, pos)

    def remove(self, args):
        if args["fullName"] not in TABLES:
            return
        dim, pos = args["dimension"], (args["x"], args["y"], args["z"])
        if (dim, pos) in self.busy:
            return
        self._return_inventory(dim, pos)
