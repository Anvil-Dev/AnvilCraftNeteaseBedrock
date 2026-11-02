# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""将原版铁砧吸到磁铁下方，通电时还原原版重力方块并释放。"""

from math import floor

from anvilcraft_scripts.common.magnets import HELD, MAGNETS, PASSABLE
from anvilcraft_scripts.server.inventory import Inventories


class MagnetWork(object):
    """吸起和释放均先保存恢复凭据，区块未加载时保留凭据。"""

    def __init__(self, api, log, stations, can_lift):
        self._factory, self._level = api.GetEngineCompFactory(), api.GetLevelId()
        self._log, self._stations = log, stations
        self._can_lift = can_lift
        self._data = Inventories(self._factory, self._level, log, "anvilcraft:magnet_holds_v1")
        self._busy = set()
        self._taken = {}
        self._released = set()
        self._release_started = set()
        self._reported = set()

    def _block(self, dim, pos):
        block = self._factory.CreateBlockInfo(self._level).GetBlockNew(tuple(pos), dim)
        return {"name": block["name"], "aux": block.get("aux", 0)} if block else None

    def _loaded(self, dim, pos):
        return self._factory.CreateChunkSource(self._level).CheckChunkState(dim, tuple(pos))

    def _put(self, dim, pos, value):
        blocks = self._factory.CreateBlockInfo(self._level)
        result = blocks.SetBlockNew(tuple(pos), value, 0, dim)
        return result or self._block(dim, pos) == value

    def _powered(self, dim, pos):
        redstone = self._factory.CreateRedStone(self._level)
        return redstone.GetBlockPoweredState(tuple(pos), dim) or redstone.GetStrength(tuple(pos), dim) > 0

    def _find(self, dim, pos):
        x, y, z = pos
        for distance in range(1, 6):
            source = (x, y - distance, z)
            if not self._loaded(dim, source) or (dim, source) in self._busy:
                return None
            block = self._block(dim, source)
            if not block:
                return None
            if block["name"] in HELD:
                return (source, block) if self._can_lift(dim, source) else None
            if block["name"] not in PASSABLE:
                return None
        return None

    def _refund(self, dim, pos, record):
        if self._clear(dim, pos):
            block = record["anvil"]
            self._stations.send(dim, (pos[0] + 0.5, pos[1] - 0.5, pos[2] + 0.5), [
                {"newItemName": block["name"], "newAuxValue": block["aux"], "count": 1}])

    def _clear(self, dim, pos):
        if not self._data.write(dim, pos, None):
            return False
        key = (dim, pos)
        self._taken.pop(key, None)
        self._released.discard(key)
        self._release_started.discard(key)
        self._reported.discard(key)
        return True

    def _uncertain(self, dim, pos, record):
        key = (dim, pos)
        if key not in self._reported:
            self._log.error("[AnvilCraft] magnet needs reconciliation dim=%s pos=%s record=%r", dim, pos, record)
            self._reported.add(key)

    def _path_clear(self, dim, pos, record, held):
        for y in range(record["source"][1] + 1, pos[1]):
            cell = (pos[0], y, pos[2])
            if not self._loaded(dim, cell):
                return False
            block = self._block(dim, cell)
            if not block or (block["name"] not in PASSABLE and block != held):
                return False
        return True

    def _resume(self, dim, pos, record):
        source, target = tuple(record["source"]), (pos[0], pos[1] - 1, pos[2])
        key = (dim, pos)
        if not self._loaded(dim, target):
            return
        held = {"name": HELD[record["anvil"]["name"]], "aux": record["anvil"]["aux"] & 3}
        phase = record["phase"]
        if phase == "taking":
            if not self._loaded(dim, source):
                return
            if key not in self._taken:
                self._uncertain(dim, pos, record)
                return
            if not self._taken[key]:
                magnet = self._block(dim, pos)
                if self._block(dim, source) != record["anvil"] or not magnet or magnet["name"] not in MAGNETS:
                    self._clear(dim, pos)
                    return
                if self._powered(dim, pos) or not self._path_clear(dim, pos, record, held):
                    return
                if not self._put(dim, source, {"name": "minecraft:air", "aux": 0}):
                    return
                self._taken[key] = True
            record["phase"] = "placing"
            if not self._data.write(dim, pos, record):
                return
        if record["phase"] == "placing":
            current = self._block(dim, target)
            if current != held:
                if not self._path_clear(dim, pos, record, held):
                    return
                if not current or current["name"] not in PASSABLE:
                    self._refund(dim, pos, record)
                    return
                if not self._put(dim, target, held):
                    return
            record["phase"] = "held"
            if not self._data.write(dim, pos, record):
                return
        current = self._block(dim, target)
        magnet = self._block(dim, pos)
        if record["phase"] == "releasing":
            if key not in self._released:
                if current == held:
                    if not self._put(dim, target, record["anvil"]):
                        return
                    self._released.add(key)
                elif key in self._release_started:
                    self._refund(dim, pos, record)
                    return
                else:
                    self._uncertain(dim, pos, record)
                    return
            record["phase"] = "released"
            if self._data.write(dim, pos, record):
                self._clear(dim, pos)
        elif record["phase"] == "released":
            self._clear(dim, pos)
        elif current != held:
            self._refund(dim, pos, record)
        elif not magnet or magnet["name"] not in MAGNETS or self._powered(dim, pos):
            record["phase"] = "releasing"
            if self._data.write(dim, pos, record):
                self._release_started.add(key)
                self._resume(dim, pos, record)

    def step(self, dim, pos):
        target = (pos[0], pos[1] - 1, pos[2])
        keys = {(dim, pos), (dim, target)}
        if keys & self._busy or not self._loaded(dim, pos):
            return
        record = self._data.get(dim, pos)
        fresh = "phase" not in record
        if "source" in record:
            keys.add((dim, tuple(record["source"])))
        if fresh:
            block = self._block(dim, pos)
            if not block or block["name"] not in MAGNETS or self._powered(dim, pos):
                return
            found = self._find(dim, pos)
            if not found:
                return
            source, anvil = found
            keys.add((dim, source))
            record = {"items": [], "phase": "taking", "source": list(source), "anvil": anvil}
        if keys & self._busy:
            return
        self._busy.update(keys)
        try:
            if fresh and not self._data.write(dim, pos, record):
                return
            if fresh:
                self._taken[dim, pos] = False
            self._resume(dim, pos, record)
        finally:
            self._busy.difference_update(keys)

    def block_tick(self, args):
        if args["blockName"] in MAGNETS:
            self.step(args["dimension"], (args["posX"], args["posY"], args["posZ"]))

    def advance(self, tick):
        if tick % 30 == 0:
            for dim, pos, _ in self._data.scan(16):
                self.step(dim, pos)

    def remove(self, args):
        name = args["fullName"]
        dim, cell = args["dimension"], (args["x"], args["y"], args["z"])
        if name in MAGNETS:
            # 拆除事件可能在方块替换完成前发出，下一次恢复扫描会释放铁砧。
            return
        if name in HELD.values():
            pos = (cell[0], cell[1] + 1, cell[2])
            if (dim, cell) not in self._busy:
                record = self._data.get(dim, pos)
                if record.get("phase") == "held":
                    self._refund(dim, pos, record)

    def lightning(self, args):
        if args.get("engineTypeStr") != "minecraft:lightning_bolt":
            return
        dim = args["dimensionId"]
        x, y, z = (int(floor(args[axis])) for axis in ("posX", "posY", "posZ"))
        for depth in (0, 1):
            block = self._block(dim, (x, y - depth, z))
            if block and block["name"] == "minecraft:lightning_rod":
                y -= depth + 1
                break
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for dy in range(3):
                    pos = (x + dx, y - dy, z + dz)
                    if self._loaded(dim, pos):
                        block = self._block(dim, pos)
                        if block and block["name"] == "minecraft:iron_block":
                            self._put(dim, pos, {"name": MAGNETS[1], "aux": 0})
