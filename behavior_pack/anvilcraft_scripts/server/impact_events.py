# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""将专用重力事件和原版下落实体的生命周期配对到同一次加工。"""

from anvilcraft_scripts.common.impact import VANILLA_ANVILS, FallingAnvils, crush_at
from anvilcraft_scripts.common.drop_recipes import RECIPES, TABLES
from anvilcraft_scripts.server.drop_work import DropWork
from anvilcraft_scripts.server.block_work import BlockWork
from anvilcraft_scripts.server.stations import Stations
from anvilcraft_scripts.server.magnet_work import MagnetWork
from anvilcraft_scripts.server.logistics_work import LogisticsWork


def _nbt_value(tag):
    if isinstance(tag, dict) and "__value__" in tag:
        return tag["__value__"]
    return tag


def _falling_material(nbt):
    root = _nbt_value(nbt)
    block = _nbt_value(root.get("FallingBlock")) if isinstance(root, dict) else None
    if isinstance(block, dict):
        return _nbt_value(block.get("name"))
    return None


class _VanillaFall(object):

    def __init__(self, dimension, origin, start_y, tick):
        self.dimension = dimension
        self.origin = origin
        self.last_cell = origin
        self.start_y = self.last_y = start_y
        self.down_step = 0
        self.started = tick
        self.landing = None
        self.support = None
        self.ended = None

    def can_reach_landing(self):
        if self.landing is None or self.last_y >= self.start_y:
            return False
        x, y, z = self.landing
        # 两次脚本采样可能落在同一个物理帧，保留最近一次实际下降量。
        return ((self.last_cell[0], self.last_cell[2]) == (x, z) and
                0 <= self.last_cell[1] - y <= self.down_step + 1)


class ImpactEvents(object):
    """接收 ModSDK 回调，按实体 ID 去重，并在服务端确认实际落点。"""

    def __init__(self, api, logger):
        self._api = api
        self._log = logger
        self._factory = api.GetEngineCompFactory()
        self._level = api.GetLevelId()
        self._blocks = self._factory.CreateBlockInfo(self._level)
        self._anvils = set(VANILLA_ANVILS)
        self._falls = FallingAnvils()
        self._vanilla = {}
        self._tick = 0
        self._reported_missing_material = False
        self._block_work = BlockWork(api, logger)

    def listen(self, system):
        self._drop_work = DropWork(self._api, system, self._log)
        self._stations = Stations(self._api, system, self._log, self._drop_work)
        self._magnets = MagnetWork(self._api, self._log, self._stations, self._can_lift)
        self._logistics = LogisticsWork(self._api, self._log, self._stations, self._drop_work)
        for event, callback in (
            ("LoadServerAddonScriptsAfter", self._load_tags),
            ("HeavyBlockStartFallingServerEvent", self._start),
            ("FallingBlockReturnHeavyBlockServerEvent", self._land),
            ("FallingBlockBreakServerEvent", self._break),
            ("AddEntityServerEvent", self._add_entity),
            ("OnGroundServerEvent", self._on_ground),
            ("EntityRemoveEvent", self._remove_entity),
            ("ChunkAcquireDiscardedServerEvent", self._unload),
            ("OnScriptTickServer", self._advance),
            ("ServerBlockUseEvent", self._machine_use),
            ("ServerBlockEntityTickEvent", self._machine_tick),
            ("BlockRemoveServerEvent", self._machine_remove),
        ):
            system.ListenForEvent(self._api.GetEngineNamespace(), self._api.GetEngineSystemName(),
                                  event, self, callback)

    def _machine_use(self, args):
        self._stations.use(args)
        self._logistics.use(args)

    def _machine_tick(self, args):
        self._stations.block_tick(args)
        self._magnets.block_tick(args)
        self._logistics.block_tick(args)

    def _machine_remove(self, args):
        self._stations.remove(args)
        self._magnets.remove(args)
        self._logistics.remove(args)

    def _can_lift(self, dim, pos):
        return not any(fall.dimension == dim and fall.landing == pos
                       for fall in self._vanilla.itervalues())

    def _load_tags(self, args):
        self._drop_work.load()
        self._block_work.load()
        blocks = self._factory.CreateBlock(self._level)
        for block in blocks.LookupBlocksByBlockTag("anvilcraft:impact_anvils") or ():
            self._anvils.add(block["blockName"])
        self._log.info("[AnvilCraft] impact_anvils=%s", sorted(self._anvils))

    def close(self):
        self._drop_work.close()
        self._block_work.close()

    def _start(self, args):
        name = args["blockName"]
        if name in self._anvils:
            pos = (args["blockX"], args["blockY"], args["blockZ"])
            self._falls.start(args["dimensionId"], args["fallingBlockId"], name, pos, self._tick)

    def _land(self, args):
        name = args["heavyBlockName"]
        if name in self._anvils:
            pos = (args["blockX"], args["blockY"], args["blockZ"])
            self._settle(args["dimensionId"], args["fallingBlockId"], name, pos, "gravity")

    def _settle(self, dimension, entity, name, pos, source):
        target = self._falls.land(dimension, entity, name, pos)
        fall = self._vanilla.get(str(entity))
        expected = None
        if fall and fall.dimension == dimension and fall.landing == pos:
            expected = fall.support
        self._forget_vanilla(dimension, str(entity))
        if target is None:
            return
        # 同一格只出现了一块铁砧，其他实体的射线候选不能再次消费锅内的原料。
        for other in self._vanilla.itervalues():
            if other.dimension == dimension and other.landing == pos:
                other.landing = None
        # 双方块配方已匹配但写入失败时，也不能继续粉碎其原料。
        if self._block_work.process(dimension, target, expected):
            return
        support = self._blocks.GetBlockNew(target, dimension) or {}
        platform = support.get("name")
        if platform in RECIPES and (expected is None or expected == platform):
            if platform in TABLES:
                self._stations.process(platform, dimension, target)
            else:
                self._drop_work.process(platform, dimension, target, self._tick)
            return
        result = crush_at(self._blocks, dimension, target, expected)
        if result:
            self._log.info("[AnvilCraft] crush source=%s dim=%s pos=%s result=%s",
                           source, dimension, target, result)
        else:
            block = self._blocks.GetBlockNew(target, dimension) or {}
            self._log.info("[AnvilCraft] no crush source=%s dim=%s pos=%s below=%s",
                           source, dimension, target, block.get("name"))

    def _break(self, args):
        if args["blockName"] in self._anvils:
            self._discard(args["dimensionId"], str(args["fallingBlockId"]))

    def _discard(self, dimension, entity):
        self._forget_vanilla(dimension, entity)
        self._falls.discard(dimension, entity)

    def _forget_vanilla(self, dimension, entity):
        fall = self._vanilla.get(entity)
        if fall is not None and fall.dimension == dimension:
            del self._vanilla[entity]

    def _add_entity(self, args):
        self._magnets.lightning(args)
        if args["engineTypeStr"] != "minecraft:falling_block":
            return
        entity = str(args["id"])
        dimension = args["dimensionId"]
        pos = (args["posX"], args["posY"], args["posZ"])
        origin = self._api.GetIntPos(pos)
        nbt = self._factory.CreateEntityDefinitions(entity).GetEntityNBTTags()
        name = _falling_material(nbt)
        if not name:
            # 引擎在移除起点方块之前创建实体时，也可从原位置取得方块名。
            name = (self._blocks.GetBlockNew(origin, dimension) or {}).get("name")
            if name in (None, "minecraft:air") and not self._reported_missing_material:
                self._reported_missing_material = True
                self._log.warning("[AnvilCraft] falling block material unavailable id=%s pos=%s",
                                  entity, origin)
        if name not in VANILLA_ANVILS or entity in self._vanilla:
            return
        self._falls.start(dimension, entity, name, origin, self._tick)
        fall = _VanillaFall(dimension, origin, pos[1], self._tick)
        self._vanilla[entity] = fall
        self._observe(fall, pos)
        self._log.info("[AnvilCraft] falling anvil id=%s dim=%s pos=%s", entity, dimension, origin)

    def _observe(self, fall, pos):
        fall.last_cell = self._api.GetIntPos(pos)
        if pos[1] != fall.last_y:
            fall.down_step = max(0, fall.last_y - pos[1])
            fall.last_y = pos[1]
        # 提前记录铁砧将落入的格子。实体移除时可能已取不到坐标，也可能碎成物品。
        only_blocks = self._api.GetMinecraftEnum().RayFilterType.OnlyBlocks
        hits = self._api.getEntitiesOrBlockFromRay(fall.dimension, pos, (0, -1, 0), 12,
                                                   False, only_blocks)
        if not hits:
            fall.landing = None
            return
        hit = hits[0]
        x, y, z = hit["pos"]
        if hit["identifier"] in VANILLA_ANVILS:
            # 上方还有一个下落实体时，挡在它前面的铁砧不属于这次落地。
            if fall.landing != (x, y, z) or fall.last_cell != (x, y, z):
                fall.landing = None
            return
        fall.landing = (x, y + 1, z) if y + 1 < fall.origin[1] else None
        fall.support = hit["identifier"]

    def _on_ground(self, args):
        entity = str(args["id"])
        fall = self._vanilla.get(entity)
        if fall is None:
            return
        pos = self._factory.CreatePos(entity).GetFootPos()
        if pos is not None:
            self._observe(fall, pos)

    def _remove_entity(self, args):
        fall = self._vanilla.get(str(args["id"]))
        if fall is not None and fall.ended is None:
            fall.ended = self._tick

    def _advance(self):
        self._tick += 1
        self._stations.advance(self._tick)
        self._magnets.advance(self._tick)
        self._logistics.advance(self._tick)
        self._drop_work.tick(self._tick)
        self._block_work.tick(self._tick)
        for entity, fall in self._vanilla.items():
            if self._tick - fall.started >= 1200:
                self._discard(fall.dimension, entity)
                continue
            if fall.ended is None:
                pos = self._factory.CreatePos(entity).GetFootPos()
                if pos is not None:
                    self._observe(fall, pos)
                    continue
                fall.ended = self._tick
            if fall.can_reach_landing():
                placed = self._blocks.GetBlockNew(fall.landing, fall.dimension) or {}
                if placed.get("name") in VANILLA_ANVILS:
                    self._settle(fall.dimension, entity, placed["name"], fall.landing, "entity")
                    continue
            if self._tick - fall.ended >= 2:
                self._discard(fall.dimension, entity)
        if self._tick % 300 == 0:
            self._falls.expire(self._tick - 1200)

    def _unload(self, args):
        dimension = args["dimension"]
        chunk = (args["chunkPosX"], args["chunkPosZ"])
        entities = set(str(entity) for entity in args["entities"] or ())
        for entity, fall in self._vanilla.items():
            if fall.dimension != dimension:
                continue
            if entity in entities or any((p[0] // 16, p[2] // 16) == chunk
                                         for p in (fall.origin, fall.last_cell)):
                self._discard(dimension, entity)
        self._falls.unload(dimension, chunk[0], chunk[1], entities)
