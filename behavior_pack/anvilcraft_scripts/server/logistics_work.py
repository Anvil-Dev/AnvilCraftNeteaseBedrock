# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""溜槽与磁力溜槽的收集、过滤、搬运和原版容器交换。"""

from copy import deepcopy

from anvilcraft_scripts.common.drop_recipes import TABLES, item_name
from anvilcraft_scripts.common.logistics import (
    CHUTE, COLLECTION_AREA, CONTAINERS, DIRECTIONS, LOGISTICS, MAGNETIC_CHUTE, offset, placement_facing,
)
from anvilcraft_scripts.server.inventory import insert, stack_equal


class LogisticsWork(object):
    """机器库存间一次保存，原版容器交换保存扣料前后快照以便恢复。"""

    def __init__(self, api, log, stations, drop_work):
        self._api = api
        self._factory, self._level = api.GetEngineCompFactory(), api.GetLevelId()
        self._log, self._stations, self._drops = log, stations, drop_work
        self._inventory = stations.inventory
        self._busy = stations.busy
        self._cooldown = {}
        self._used = {}
        self._reported = set()
        self._decisions = {}

    def load(self):
        whitelist = self._factory.CreateBlockUseEventWhiteList(self._level)
        for name in sorted(CONTAINERS):
            if not whitelist.AddBlockItemListenForUseEvent(name):
                self._log.warning("[AnvilCraft] could not register chute placement on %s", name)

    def _name(self, dim, pos):
        if not self._factory.CreateChunkSource(self._level).CheckChunkState(dim, pos):
            return None
        block = self._factory.CreateBlockInfo(self._level).GetBlockNew(pos, dim) or {}
        return block.get("name")

    def _record(self, dim, pos):
        return self._inventory.get(dim, pos)

    def _facing(self, dim, pos):
        states = self._factory.CreateBlockState(self._level).GetBlockStates(pos, dim) or {}
        return states.get("facing_direction", 0)

    def place(self, args):
        name = args["fullName"]
        if name not in LOGISTICS or args.get("cancel"):
            return
        face = args["face"]
        if face not in range(6):
            return
        dim, pos = args["dimensionId"], (args["x"], args["y"], args["z"])
        player = args["entityId"]
        sneaking = self._factory.CreatePlayer(player).isSneaking()
        look = self._api.GetDirFromRot(self._factory.CreateRot(player).GetRot()) if name == MAGNETIC_CHUTE else None
        neighbours = []
        for direction in DIRECTIONS:
            cell = offset(pos, direction)
            other = self._name(dim, cell)
            neighbours.append((other, self._facing(dim, cell) if other in LOGISTICS else None))
        facing = placement_facing(name, face, sneaking, look, neighbours)
        if facing is None:
            args["cancel"] = True
        else:
            args["auxData"] = facing

    def attach(self, args):
        """手持溜槽点击容器时先放置，防止容器界面截走方块物品操作。"""
        if args.get("cancel") or (args["blockName"] not in CONTAINERS and args["blockName"] not in TABLES):
            return False
        player, dim, face = args["playerId"], args["dimensionId"], args.get("face")
        item = self._stations.carried(player)
        if not item or not item.get("count", 0) or item_name(item) not in LOGISTICS:
            return False
        args["cancel"] = True
        clicked = args["x"], args["y"], args["z"]
        if face not in range(6) or not self._stations.reachable(player, dim, clicked):
            return True
        target = offset(clicked, DIRECTIONS[face])
        key = dim, target
        if key in self._busy or self._used.get(player, -1) > self._stations.tick:
            return True
        game_type = self._factory.CreateGame(self._level).GetPlayerGameType(player)
        if game_type not in (0, 1):
            return True
        original = self._name(dim, target)
        if original not in ("minecraft:air", "minecraft:water", "minecraft:flowing_water",
                            "minecraft:lava", "minecraft:flowing_lava"):
            return True
        name = item_name(item)
        placement = dict(fullName=name, auxData=0, face=face, entityId=player, dimensionId=dim,
                         x=target[0], y=target[1], z=target[2])
        self.place(placement)
        if placement.get("cancel"):
            return True
        aux = item.get("newAuxValue", item.get("auxValue", 0))
        if not self._factory.CreateItem(player).MayPlaceOn(name, aux, clicked, face):
            return True
        self._used[player] = self._stations.tick + 8
        self._busy.add(key)
        try:
            if self._name(dim, target) != original or self._stations.carried(player) != item:
                return True
            if game_type == 0 and not self._stations.replace_carried(player, item, 1):
                return True
            placed = False
            if self._name(dim, target) == original:
                placed = self._factory.CreateBlockInfo(self._level).SetBlockNew(
                    target, {"name": name, "aux": placement["auxData"]}, 0, dim)
                placed = placed or self._name(dim, target) == name
            if not placed and game_type == 0:
                refund = deepcopy(item)
                refund["count"] = 1
                self._stations.send(dim, self._factory.CreatePos(player).GetFootPos(), [refund])
        finally:
            self._busy.remove(key)
        return True

    def _native(self, dim, pos):
        name = self._name(dim, pos)
        if name not in CONTAINERS and not (name and name.endswith("_shulker_box")):
            return None
        items = self._factory.CreateItem(self._level)
        count = items.GetContainerSize(pos, dim)
        if not 0 < count <= 108:
            return None
        contents = []
        for slot in range(count):
            item = items.GetContainerItem(pos, slot, dim, True)
            contents.append(item if item and item.get("count", 0) > 0 else None)
        return name, contents

    def _accept(self, record, name, item):
        wanted = record.get("filter")
        variant = item.get("newAuxValue", item.get("auxValue", 0))
        if wanted and wanted != [item_name(item), variant]:
            return record["items"], 0
        return insert(record["items"], item, 8 if name in TABLES else 9,
                      self._stations.maximum(item), name in TABLES)

    def _recover(self, dim, pos, applied=None):
        record = self._record(dim, pos)
        receipt = record.get("transfer")
        if not receipt:
            return True
        key = (dim, pos)
        if applied is None:
            applied = receipt.get("outcome", self._decisions.get(key))
        if applied is None:
            if key not in self._reported:
                self._log.error("[AnvilCraft] transfer needs reconciliation dim=%s pos=%s receipt=%r",
                                dim, pos, receipt)
                self._reported.add(key)
            return False
        self._decisions[key] = applied
        if "outcome" not in receipt:
            receipt["outcome"] = applied
            if not self._inventory.write(dim, pos, record):
                return False
        if applied and receipt["op"] == "pull":
            record["items"] = receipt["result"]
        elif not applied and receipt["op"] == "push":
            record["items"] = receipt["original"]
        del record["transfer"]
        saved = self._inventory.write(dim, pos, record)
        if saved:
            self._decisions.pop(key, None)
            self._reported.discard(key)
        return saved

    def _native_exchange(self, dim, pos, native_pos, snapshot, slot, after, record, receipt):
        name, items = snapshot
        receipt.update(native=list(native_pos), name=name, slot=slot, before=items[slot], after=after)
        record["transfer"] = receipt
        record["logistics"] = True
        if not self._inventory.write(dim, pos, record):
            return False
        current = self._native(dim, native_pos)
        if current != snapshot:
            self._recover(dim, pos, False)
            return False
        component = self._factory.CreateItem(self._level)
        success = component.SpawnItemToContainer(after or {}, slot, native_pos, dim)
        applied = True if success else None
        if not success:
            current = self._native(dim, native_pos)
            if current == snapshot:
                applied = False
        self._recover(dim, pos, applied)
        return applied is True

    def _move(self, dim, source, target, limit=64):
        source_name, target_name = self._name(dim, source), self._name(dim, target)
        if source_name not in LOGISTICS or (dim, target) in self._busy:
            return 0
        record = self._record(dim, source)
        if record.get("transfer") or not record["items"]:
            return 0
        payload = deepcopy(record["items"][0])
        payload["count"] = min(payload["count"], limit)
        target_record = self._record(dim, target) if target_name in TABLES + LOGISTICS else None
        if target_record is not None:
            if target_record.get("transfer"):
                return 0
            contents, take = self._accept(target_record, target_name, payload)
            if not take:
                return 0
            target_record["items"] = contents
            if target_name in LOGISTICS:
                target_record["logistics"] = True
            record["items"][0]["count"] -= take
            record["items"] = [item for item in record["items"] if item["count"]]
            keys = {(dim, source), (dim, target)}
            owned = keys - self._busy
            self._busy.update(owned)
            try:
                saved = self._inventory.change([(dim, source, record), (dim, target, target_record)])
                return take if saved else 0
            finally:
                self._busy.difference_update(owned)
        native = self._native(dim, target)
        if not native:
            return 0
        name, items = native
        for slot, existing in enumerate(items):
            if existing is not None and not stack_equal(existing, payload):
                continue
            maximum = self._stations.maximum(payload)
            take = min(payload["count"], maximum - (existing["count"] if existing else 0))
            if take <= 0:
                continue
            after = deepcopy(existing or payload)
            after["count"] = (existing["count"] if existing else 0) + take
            original = deepcopy(record["items"])
            reserved = deepcopy(payload)
            reserved["count"] = take
            record["items"][0]["count"] -= take
            record["items"] = [item for item in record["items"] if item["count"]]
            self._busy.add((dim, target))
            try:
                saved = self._native_exchange(dim, source, target, native, slot, after, record,
                                               {"op": "push", "original": original, "reserved": [reserved]})
                return take if saved else 0
            finally:
                self._busy.remove((dim, target))
        return 0

    def _pull(self, dim, pos, source):
        if (dim, source) in self._busy:
            return
        name = self._name(dim, source)
        if name in LOGISTICS:
            facing = self._facing(dim, source)
            if facing not in range(6) or offset(source, DIRECTIONS[facing]) != pos:
                return
            # 当前节点已持有位置锁，暂时让出给同一次服务端交换。
            self._busy.remove((dim, pos))
            try:
                return self._move(dim, source, pos)
            finally:
                self._busy.add((dim, pos))
        if name in TABLES:
            return
        native = self._native(dim, source)
        if native:
            record = self._record(dim, pos)
            for slot, item in enumerate(native[1]):
                if not item:
                    continue
                contents, take = self._accept(record, self._name(dim, pos), item)
                if not take:
                    continue
                rest = deepcopy(item)
                rest["count"] -= take
                reserved = deepcopy(item)
                reserved["count"] = take
                self._busy.add((dim, source))
                try:
                    return self._native_exchange(dim, pos, source, native, slot, rest if rest["count"] else None,
                                                 record, {"op": "pull", "result": contents, "reserved": [reserved]})
                finally:
                    self._busy.remove((dim, source))
            return
        if name is None:
            return
        return self._collect(dim, pos, source)

    def _collect(self, dim, pos, source):
        for drop in self._drops.snapshot(COLLECTION_AREA, dim, source):
            record = self._record(dim, pos)
            if record.get("transfer"):
                return
            contents, take = self._accept(record, self._name(dim, pos), drop.item)
            if not take:
                continue
            if not self._drops.take(drop, COLLECTION_AREA, dim, source, self._stations.tick):
                continue
            record["items"], record["logistics"] = contents, True
            remaining = deepcopy(drop.item)
            remaining["count"] -= take
            saved = self._inventory.write(dim, pos, record)
            if not saved:
                remaining = drop.item
            if remaining["count"]:
                self._stations.send(dim, drop.pos, [remaining])
            return saved

    def _eject(self, dim, pos, target, direction, magnetic):
        if self._name(dim, target) != "minecraft:air":
            return
        record = self._record(dim, pos)
        if not record["items"] or record.get("transfer"):
            return
        payload = deepcopy(record["items"][0])
        nearby = self._drops.snapshot(COLLECTION_AREA, dim, target)
        present = sum(drop.item["count"] for drop in nearby if item_name(drop.item) == item_name(payload))
        take = min(payload["count"], max(0, self._stations.maximum(payload) - present))
        if not take:
            return
        record["items"][0]["count"] -= take
        record["items"] = [item for item in record["items"] if item["count"]]
        if self._inventory.write(dim, pos, record):
            payload["count"] = take
            point = tuple(value + 0.5 for value in target)
            motion = tuple(value * (0.25 if magnetic else 0) for value in direction)
            self._drops.deliver(dim, [(point, payload, motion)])
            return True

    def inside(self, args):
        name = args["blockName"]
        if name not in LOGISTICS:
            return
        entity = args["entityId"]
        kind = self._factory.CreateEngineType(entity)
        if kind is None or kind.GetEngineTypeStr() != "minecraft:item":
            return
        dimension = self._factory.CreateDimension(entity)
        if dimension is None:
            return
        dim = dimension.GetEntityDimensionId()
        pos = args["blockX"], args["blockY"], args["blockZ"]
        key = dim, pos
        if key in self._busy or self._cooldown.get(key, 0) > 0 or self._name(dim, pos) != name:
            return
        redstone = self._factory.CreateRedStone(self._level)
        if redstone.GetBlockPoweredState(pos, dim) or redstone.GetStrength(pos, dim) > 0:
            return
        self._busy.add(key)
        try:
            if self._recover(dim, pos) and self._collect(dim, pos, pos):
                self._cooldown[key] = 8
        finally:
            self._busy.remove(key)
            self._orphan(dim, pos)

    def block_tick(self, args):
        name = args["blockName"]
        if name not in LOGISTICS:
            return
        dim, pos = args["dimension"], (args["posX"], args["posY"], args["posZ"])
        key = (dim, pos)
        if key in self._busy or self._name(dim, pos) != name:
            return
        self._cooldown[key] = max(0, self._cooldown.get(key, 0) - 1)
        if self._cooldown[key]:
            return
        self._busy.add(key)
        try:
            if not self._recover(dim, pos):
                return
            redstone = self._factory.CreateRedStone(self._level)
            if redstone.GetBlockPoweredState(pos, dim) or redstone.GetStrength(pos, dim) > 0:
                return
            facing = self._facing(dim, pos)
            if name == CHUTE and facing == 1:
                if not self._factory.CreateBlockState(self._level).SetBlockStates(pos, {"facing_direction": 0}, dim):
                    self._log.warning("[AnvilCraft] could not correct chute direction dim=%s pos=%s", dim, pos)
                    return
                facing = 0
            if facing not in range(6):
                return
            direction = DIRECTIONS[facing]
            target = offset(pos, direction)
            worked = self._move(dim, pos, target)
            if not worked:
                worked = self._eject(dim, pos, target, direction, name == MAGNETIC_CHUTE)
            if not self._record(dim, pos).get("transfer") and self._name(dim, pos) == name:
                source = offset(pos, (0, 1, 0) if name == CHUTE else tuple(-n for n in direction))
                worked = self._pull(dim, pos, source) or worked
                # 掉落物可以落入槽体内部，Java 的碰撞收集独立于入口格吸取。
                if not self._record(dim, pos).get("transfer") and self._name(dim, pos) == name:
                    worked = self._collect(dim, pos, pos) or worked
            if worked:
                self._cooldown[key] = 8
        finally:
            self._busy.remove(key)
            self._orphan(dim, pos)

    def _orphan(self, dim, pos):
        name = self._name(dim, pos)
        if name is None or name in LOGISTICS:
            return
        self._cooldown.pop((dim, pos), None)
        self._refund(dim, pos)

    def _refund(self, dim, pos):
        key = (dim, pos)
        if key in self._busy:
            return
        self._busy.add(key)
        try:
            self._refund_locked(dim, pos)
        finally:
            self._busy.remove(key)

    def _refund_locked(self, dim, pos):
        record = self._record(dim, pos)
        if record.get("transfer") and not self._recover(dim, pos):
            # 保留有争议的转账凭据，先退还机器中无争议的其余库存。
            record = self._record(dim, pos)
            items, record["items"] = record["items"], []
            receipt = record["transfer"]
            receipt["original" if receipt["op"] == "push" else "result"] = receipt["reserved"]
            if self._inventory.write(dim, pos, record):
                self._stations.send(dim, tuple(value + 0.5 for value in pos), items)
            return
        record = self._record(dim, pos)
        if self._inventory.write(dim, pos, None):
            self._stations.send(dim, tuple(value + 0.5 for value in pos), record["items"])

    def advance(self, tick):
        if tick % 30 == 0:
            for dim, pos, record in self._inventory.scan(16, "logistics"):
                if record.get("logistics") and (dim, pos) not in self._busy:
                    self._orphan(dim, pos)

    def remove(self, args):
        if args["fullName"] in LOGISTICS:
            # 保存失败和同步重入都由加载位置的恢复扫描补退库存。
            dim, pos = args["dimension"], (args["x"], args["y"], args["z"])
            self._refund(dim, pos)

    def use(self, args):
        name = args["blockName"]
        if name not in LOGISTICS:
            return
        item = self._stations.carried(args["playerId"])
        if item and item.get("count", 0) > 0 and item_name(item) in LOGISTICS:
            return
        args["cancel"] = True
        player, dim, face = args["playerId"], args["dimensionId"], args.get("face")
        pos = (args["x"], args["y"], args["z"])
        key = (dim, pos)
        tick = self._stations.tick
        if (key in self._busy or face not in range(6) or self._used.get(player, -1) > tick
                or not self._stations.reachable(player, dim, pos) or self._name(dim, pos) != name):
            return
        record = self._record(dim, pos)
        if record.get("transfer"):
            return
        self._used[player] = tick + 8
        self._busy.add(key)
        try:
            record["logistics"] = True
            item = self._stations.carried(player)
            if self._factory.CreatePlayer(player).isSneaking():
                if item and item.get("count", 0):
                    wanted = [item_name(item), item.get("newAuxValue", item.get("auxValue", 0))]
                    record["filter"] = None if record.get("filter") == wanted else wanted
                    self._inventory.write(dim, pos, record)
                elif name != CHUTE or face != 1:
                    if not self._factory.CreateBlockState(self._level).SetBlockStates(pos, {"facing_direction": face}, dim):
                        self._log.warning("[AnvilCraft] could not set chute direction dim=%s pos=%s face=%s",
                                          dim, pos, face)
                return
            if item and item.get("count", 0):
                contents, take = self._accept(record, name, item)
                if take and self._stations.replace_carried(player, item, take):
                    record["items"] = contents
                    if not self._inventory.write(dim, pos, record):
                        refund = deepcopy(item)
                        refund["count"] = take
                        self._stations.send(dim, self._factory.CreatePos(player).GetFootPos(), [refund])
            elif record["items"]:
                items, record["items"] = record["items"], []
                if self._inventory.write(dim, pos, record):
                    self._stations.send(dim, (pos[0] + 1.25, pos[1] + 0.5, pos[2] + 0.5), items)
        finally:
            self._busy.remove(key)
            self._orphan(dim, pos)
