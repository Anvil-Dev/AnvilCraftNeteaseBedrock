# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""根据相邻出口切换溜槽形态，保存转换凭据并恢复含水与冷却。"""

from copy import deepcopy
from random import getrandbits

from anvilcraft_scripts.common.logistics import (
    CHUTES, COOLDOWN_KEY, DOWN_CHUTES, LOGISTICS, ORDINARY_CHUTES, SIMPLE_CHUTES,
    chute_form, DIRECTIONS, offset,
)
from anvilcraft_scripts.server.inventory import Inventories, stack_equal


class ChuteForms(object):
    """隐藏的方块类型表示方向与高接头状态，世界库存始终按位置保存。"""

    def __init__(self, api, log, stations, drops):
        self._factory, self._level = api.GetEngineCompFactory(), api.GetLevelId()
        self._log, self._inventory, self._busy = log, stations.inventory, stations.busy
        self._maximum, self._drops = stations.maximum, drops
        self._data = Inventories(self._factory, self._level, log, "anvilcraft:chute_forms_v1")
        self._issued = set()
        self._reported = set()

    def block(self, dim, pos):
        """只读取已加载位置，附加值用于核对转换期间是否被其他操作改变。"""
        if not self._factory.CreateChunkSource(self._level).CheckChunkState(dim, pos):
            return None
        value = self._factory.CreateBlockInfo(self._level).GetBlockNew(pos, dim)
        return {"name": value["name"], "aux": value.get("aux", 0)} if value else None

    def facing(self, dim, pos, name):
        """向下形态没有朝向状态，其余形态使用原生六面朝向。"""
        if name in DOWN_CHUTES:
            return 0
        states = self._factory.CreateBlockState(self._level).GetBlockStates(pos, dim) or {}
        return states.get("facing_direction", 0)

    def neighbours(self, dim, pos):
        """邻区块未加载时返回 None，避免把未知入口当成已拆除。"""
        result = []
        for direction in DIRECTIONS:
            cell = offset(pos, direction)
            block = self.block(dim, cell)
            if block is None:
                return None
            name = block["name"]
            result.append((name, self.facing(dim, cell, name) if name in LOGISTICS else None))
        return result

    def entity_data(self, dim, pos):
        """从原生方块实体读写冷却，保留存档中的接力延时。"""
        return self._factory.CreateBlockEntityData(self._level).GetBlockEntityData(dim, pos)

    def _spill(self, dim, pos, record):
        token = record["token"]
        if not record["spill"] and record.get("phase") != "spilled":
            record["phase"] = "spilled"
            if not self._data.write(dim, pos, record):
                return False
        if record.get("phase") != "spilled":
            if record.get("phase") == "spilling" and token not in self._issued:
                if token not in self._reported:
                    self._log.error(
                        "[AnvilCraft] chute spill needs reconciliation dim=%s pos=%s record=%r",
                        dim, pos, record)
                    self._reported.add(token)
                return False
            if token not in self._issued:
                record["phase"] = "spilling"
                if not self._data.write(dim, pos, record):
                    return False
                center = tuple(value + 0.5 for value in pos)
                self._drops.deliver(dim, [(center, item) for item in record["spill"]])
                self._issued.add(token)
            if not self._drops.flush():
                return False
            record["phase"] = "spilled"
            if not self._data.write(dim, pos, record):
                return False
        inventory = self._inventory.get(dim, pos)
        if inventory.get("form_token") == token:
            del inventory["form_token"]
            block = self.block(dim, pos)
            empty = (not inventory["items"] and not inventory.get("transfer")
                     and not inventory.get("liquid"))
            remaining = None if empty and block and block["name"] not in LOGISTICS else inventory
            if not self._inventory.write(dim, pos, remaining):
                return False
        return True

    def _resume(self, dim, pos, record):
        blocks = self._factory.CreateBlockInfo(self._level)
        current = self.block(dim, pos)
        if current is None:
            return False
        before, after = record["before"], record["after"]
        spilling = "spill" in record
        inventory = self._inventory.get(dim, pos)
        if record.get("phase") not in ("spilling", "spilled") and current in (before, after) and (
                (before["name"] in SIMPLE_CHUTES) != (after["name"] in SIMPLE_CHUTES)):
            if inventory.get("transfer"):
                return False
            inventory["logistics"] = True
            if after["name"] in SIMPLE_CHUTES:
                inventory["simple_first"] = bool(inventory["items"])
                inventory.pop("filter", None)
            else:
                inventory.pop("simple_first", None)
                if spilling and inventory.get("form_token") != record["token"]:
                    if inventory["items"] != record["original"]:
                        self._log.error(
                            "[AnvilCraft] chute inventory changed dim=%s pos=%s", dim, pos)
                        return False
                    inventory["items"] = record["kept"]
                    inventory["form_token"] = record["token"]
            if not self._inventory.write(dim, pos, inventory):
                return False
            current = self.block(dim, pos)
            if current is None:
                return False
        if current == record["before"]:
            if after["name"] in SIMPLE_CHUTES:
                liquid = blocks.GetLiquidBlock(pos, dim)
                liquid = liquid if liquid and liquid.get("name") != "minecraft:air" else None
                if liquid != record.get("liquid"):
                    if liquid is None:
                        record.pop("liquid", None)
                    else:
                        record["liquid"] = liquid
                    if not self._data.write(dim, pos, record):
                        return False
                    if self.block(dim, pos) != before or blocks.GetLiquidBlock(pos, dim) != liquid:
                        return False
            blocks.SetBlockNew(pos, record["after"], 0, dim)
            current = self.block(dim, pos)
            if current == record["before"] or current is None:
                return False
        liquid = record.get("liquid")
        if liquid:
            if current["name"] == "minecraft:air":
                if not blocks.SetBlockNew(pos, liquid, 0, dim):
                    return False
            elif current["name"] in SIMPLE_CHUTES:
                if (blocks.GetLiquidBlock(pos, dim) != liquid
                        and not blocks.SetLiquidBlock(pos, liquid, dim)):
                    return False
            elif current["name"] not in CHUTES and current["name"] != liquid["name"]:
                return False
        if current == record["after"]:
            data = self.entity_data(dim, pos)
            if data is None:
                return False
            data[COOLDOWN_KEY] = record["cooldown"]
        if spilling:
            inventory = self._inventory.get(dim, pos)
            reserved = inventory.get("form_token") == record["token"]
            if reserved and current["name"] not in LOGISTICS and inventory["items"]:
                return False
            if ((reserved or record.get("phase") in ("spilling", "spilled"))
                    and not self._spill(dim, pos, record)):
                return False
        saved = self._data.write(dim, pos, None)
        if saved and spilling:
            self._issued.discard(record["token"])
            self._reported.discard(record["token"])
        return saved

    def update(self, dim, pos, facing=None):
        """在位置锁内提交类型切换，保存或引擎写入失败时保留凭据重试。"""
        key = dim, pos
        block = self.block(dim, pos)
        if key in self._busy or block is None:
            return None
        self._busy.add(key)
        try:
            pending = self._data.get(dim, pos)
            if "before" in pending:
                if not self._resume(dim, pos, pending):
                    return None
                block = self.block(dim, pos)
            name = block["name"]
            if name not in ORDINARY_CHUTES:
                return name
            neighbours = self.neighbours(dim, pos)
            if neighbours is None:
                return name
            if facing is None:
                facing = self.facing(dim, pos, name)
            if facing == 1:
                facing = 0
            desired = chute_form(name, facing, neighbours)
            if desired is None:
                return name
            target, facing = desired
            after = {"name": target, "aux": facing}
            if block == after:
                return name
            inventory = self._inventory.get(dim, pos)
            if inventory.get("transfer"):
                return None
            data = self.entity_data(dim, pos)
            if data is None:
                return None
            changed_kind = (name in SIMPLE_CHUTES) != (target in SIMPLE_CHUTES)
            cooldown = 0 if changed_kind else data[COOLDOWN_KEY] or 0
            record = {"items": [], "before": block, "after": after, "cooldown": cooldown}
            if name in SIMPLE_CHUTES and target in CHUTES and inventory["items"]:
                original = deepcopy(inventory["items"])
                first = deepcopy(original[0])
                remaining = self._maximum(first)
                kept, spill = [], []
                for item in original:
                    take = min(item["count"], remaining) if stack_equal(item, first) else 0
                    if take:
                        if not kept:
                            kept = [dict(item, count=0)]
                        kept[0]["count"] += take
                        remaining -= take
                    if take < item["count"]:
                        spill.append(dict(item, count=item["count"] - take))
                if spill or kept != original:
                    record.update(original=original, kept=kept, spill=spill,
                                  token="%032x" % getrandbits(128))
            if target in SIMPLE_CHUTES:
                liquid = self._factory.CreateBlockInfo(self._level).GetLiquidBlock(pos, dim)
                if liquid and liquid.get("name") != "minecraft:air":
                    record["liquid"] = liquid
            if not self._data.write(dim, pos, record) or not self._resume(dim, pos, record):
                return None
            current = self.block(dim, pos)
            return current["name"] if current == after else None
        finally:
            self._busy.remove(key)

    def advance(self):
        """恢复最多十六个位置，并返回位置供物流模块处理已拆除方块的库存。"""
        positions = []
        for dim, pos, _ in self._data.scan(16):
            self.update(dim, pos)
            positions.append((dim, pos))
        return positions
