# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""在同一次落砧中修改两格方块，写入失败时恢复原状态。"""

from anvilcraft_scripts.common.block_recipes import compression, squeezed_states
from anvilcraft_scripts.common.impact import VANILLA_ANVILS
from anvilcraft_scripts.common.vanilla_catalog import BLOCK_COMPRESS, SQUEEZING

_UPPER_BLOCKS = frozenset(name for _, names, _, _ in BLOCK_COMPRESS for name in names) | set(SQUEEZING)


class BlockWork(object):
    """把未完成的双方块修改保存在世界数据中，并阻止重复加工这些位置。"""

    KEY = "anvilcraft:pending_block_changes_v1"

    def __init__(self, api, log):
        self._factory = api.GetEngineCompFactory()
        self._level = api.GetLevelId()
        self._blocks = self._factory.CreateBlockInfo(self._level)
        self._states = None
        self._store = None
        self._pending = []
        self._busy = set()
        self._log = log

    def load(self):
        if self._store is None:
            self._store = self._factory.CreateExtraData(self._level)
            self._pending = self._store.GetExtraData(self.KEY) or []

    def _save(self):
        saved = self._store.SetExtraData(self.KEY, self._pending, True)
        if not saved:
            self._log.error("[AnvilCraft] could not save block changes; pending=%r", self._pending)
        return saved

    def close(self):
        if self._store is not None:
            self._save()

    def _read(self, dim, pos):
        if not self._factory.CreateChunkSource(self._level).CheckChunkState(dim, tuple(pos)):
            return None
        block = self._blocks.GetBlockNew(tuple(pos), dim)
        states = self._states.GetBlockStates(tuple(pos), dim)
        if block is None or states is None:
            return None
        result = {"name": block["name"], "states": dict(states)}
        if block["name"] == "minecraft:cauldron":
            result["nbt"] = self._blocks.GetBlockEntityData(dim, tuple(pos))
        return result

    def _row(self, dim, pos, name):
        before = self._read(dim, pos)
        if before is None:
            return None
        states = self._states.GetBlockStatesFromAuxValue(name, 0)
        if states is None:
            return None
        return {"pos": list(pos), "mode": "block", "before": before,
                "after": {"name": name, "states": dict(states)}}

    def _plan(self, dim, pos, upper):
        lower_pos = (pos[0], pos[1] - 1, pos[2])
        lower = self._blocks.GetBlockNew(lower_pos, dim) or {}
        matched = compression(upper, lower.get("name"))
        if matched:
            self._states = self._factory.CreateBlockState(self._level)
            source, result = matched
            return source, [self._row(dim, lower_pos, result),
                            self._row(dim, pos, "minecraft:air")]
        if upper not in SQUEEZING or lower.get("name") != "minecraft:cauldron":
            return None
        self._states = self._factory.CreateBlockState(self._level)
        source, result, fluid, amount = SQUEEZING[upper]
        cauldron = self._read(dim, lower_pos)
        if cauldron is None:
            return source, []
        states = squeezed_states(cauldron["states"], fluid, amount)
        nbt = cauldron["nbt"]
        if nbt is None and cauldron["states"].get("fill_level"):
            return source, []
        if nbt:
            fields = nbt.get("__value__", nbt)
            if not isinstance(fields, dict):
                return source, []
            for key in ("PotionId", "CustomColor"):
                value = fields.get(key, -1)
                if isinstance(value, dict):
                    value = value.get("__value__")
                if value != -1:
                    return source, []
        if states is None:
            return source, []
        return source, [self._row(dim, pos, result),
                        {"pos": list(lower_pos), "mode": "state", "before": cauldron,
                         "after": dict(cauldron, states=states)}]

    def _write(self, dim, row, value):
        pos = tuple(row["pos"])
        if row["mode"] == "state":
            self._states.SetBlockStates(pos, value["states"], dim)
        else:
            aux = self._states.GetBlockAuxValueFromStates(value["name"], value["states"])
            if aux is None or aux < 0:
                return False
            self._blocks.SetBlockNew(pos, {"name": value["name"], "aux": aux}, 0, dim, True)
        return self._read(dim, pos) == value

    def _complete(self, record):
        for row in record["changes"]:
            current = self._read(record["dimension"], row["pos"])
            if current == row["after"]:
                continue
            # 压合移除上格后，铁砧可继续下落并占据这个空气格。
            if (row["after"]["name"] == "minecraft:air" and current is not None
                    and current["name"] in VANILLA_ANVILS):
                continue
            return False
        return True

    def _rollback(self, record):
        dim = record["dimension"]
        written = record["written"]
        changes = record["changes"] if written is None else [record["changes"][i] for i in written]
        restored = True
        for row in reversed(changes):
            current = self._read(dim, row["pos"])
            if current is None:
                restored = False
                continue
            before, after = row["before"], row["after"]
            if row["mode"] == "state":
                # 只撤回本次写入的方块状态，保留其他回调对锅 NBT 的修改。
                before = dict(current, name=before["name"], states=before["states"])
                after = dict(current, name=after["name"], states=after["states"])
            if current not in (before, after):
                self._log.error("[AnvilCraft] block recovery conflict dim=%s change=%r current=%r",
                                dim, row, current)
                restored = False
                continue
            if current != before and not self._write(dim, row, before):
                restored = False
        return restored

    def _clear(self, record):
        record["done"] = True
        remaining = [row for row in self._pending if row is not record]
        if self._store.SetExtraData(self.KEY, remaining, True):
            self._pending = remaining
        else:
            self._log.error("[AnvilCraft] block receipt retained; record=%r", record)

    def process(self, dim, pos, expected=None):
        occupied = {(dim, pos), (dim, (pos[0], pos[1] - 1, pos[2]))}
        if occupied & self._busy:
            return True
        if any((record["dimension"], tuple(row["pos"])) in occupied
               for record in self._pending for row in record["changes"]):
            return True
        block = self._blocks.GetBlockNew(pos, dim) or {}
        upper = block.get("name")
        if upper not in _UPPER_BLOCKS or (expected is not None and upper != expected):
            return False
        plan = self._plan(dim, pos, upper)
        if plan is None:
            return False
        source, changes = plan
        if not changes or any(row is None for row in changes):
            self._log.info("[AnvilCraft] block process skipped dim=%s pos=%s recipe=%s", dim, pos, source)
            return True
        self.load()
        self._busy.update(occupied)
        try:
            record = {"dimension": dim, "changes": changes, "done": False, "written": None}
            self._pending.append(record)
            if not self._save():
                self._pending.remove(record)
                return True
            record["written"] = []
            for index, row in enumerate(changes):
                available = self._read(dim, row["pos"]) == row["before"]
                if available:
                    record["written"].append(index)
                    available = self._write(dim, row, row["after"])
                if not available:
                    self._save()
                    if self._rollback(record):
                        self._clear(record)
                    self._log.warning("[AnvilCraft] block exchange interrupted dim=%s pos=%s recipe=%s",
                                      dim, pos, source)
                    return True
            self._clear(record)
            self._log.info("[AnvilCraft] block process dim=%s pos=%s recipe=%s", dim, pos, source)
            return True
        finally:
            self._busy.difference_update(occupied)

    def tick(self, tick):
        if tick % 30 or self._store is None or not self._pending or self._busy:
            return
        self._states = self._factory.CreateBlockState(self._level)
        try:
            for record in list(self._pending):
                self._busy.update((record["dimension"], tuple(row["pos"])) for row in record["changes"])
                if record["done"] or self._complete(record) or self._rollback(record):
                    self._clear(record)
        finally:
            self._busy.clear()
