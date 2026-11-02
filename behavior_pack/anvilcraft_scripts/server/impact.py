# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""接收引擎实际发出的重力事件，不拦截铁砧交互、伤害或掉落。"""

import mod.server.extraServerApi as server_api
from mod_log import logger

from anvilcraft_scripts.common.impact import FallingAnvils, crush_at


class ImpactSystem(server_api.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(ImpactSystem, self).__init__(namespace, name)
        self._level = server_api.GetLevelId()
        self._blocks = server_api.GetEngineCompFactory().CreateBlockInfo(self._level)
        self._anvils = set(["minecraft:anvil"])
        self._falls = FallingAnvils()
        self._tick = 0
        for event, callback in (
            ("LoadServerAddonScriptsAfter", self._load_tags),
            ("HeavyBlockStartFallingServerEvent", self._start),
            ("FallingBlockReturnHeavyBlockServerEvent", self._land),
            ("FallingBlockBreakServerEvent", self._break),
            ("ChunkAcquireDiscardedServerEvent", self._unload),
            ("OnScriptTickServer", self._advance),
        ):
            self.ListenForEvent(server_api.GetEngineNamespace(), server_api.GetEngineSystemName(),
                                event, self, callback)
        logger.info("[AnvilCraft] server ready; Minecraft=%s", server_api.GetMinecraftVersion())

    def _load_tags(self, args):
        blocks = server_api.GetEngineCompFactory().CreateBlock(self._level)
        for block in blocks.LookupBlocksByBlockTag("anvilcraft:impact_anvils") or ():
            self._anvils.add(block["blockName"])
        logger.info("[AnvilCraft] impact_anvils=%s", sorted(self._anvils))

    def _start(self, args):
        name = args["blockName"]
        if name in self._anvils:
            pos = (args["blockX"], args["blockY"], args["blockZ"])
            self._falls.start(args["dimensionId"], args["fallingBlockId"], name, pos, self._tick)

    def _land(self, args):
        name = args["heavyBlockName"]
        if name not in self._anvils:
            return
        pos = (args["blockX"], args["blockY"], args["blockZ"])
        dimension = args["dimensionId"]
        target = self._falls.land(dimension, args["fallingBlockId"], name, pos)
        if target is not None:
            result = crush_at(self._blocks, dimension, target)
            if result:
                logger.debug("[AnvilCraft] crush id=%s dim=%s pos=%s result=%s",
                             args["fallingBlockId"], dimension, target, result)

    def _break(self, args):
        if args["blockName"] in self._anvils:
            self._falls.discard(args["dimensionId"], args["fallingBlockId"])

    def _unload(self, args):
        self._falls.unload(args["dimension"], args["chunkPosX"], args["chunkPosZ"],
                           args["entities"] or ())

    def _advance(self, args):
        self._tick += 1
        if self._tick % 300 == 0:
            self._falls.expire(self._tick - 1200)
