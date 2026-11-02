# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""按实际朝向选择原仓库溜槽的竖直与侧向模型。"""

from anvilcraft_scripts.common.logistics import CHUTE


class VisualEvents(object):
    """在模型初始化后设置变量，并限量检查视野内方块的方向变化。"""

    def __init__(self, api):
        self._api = api
        self._factory = api.GetEngineCompFactory()
        self._level = api.GetLevelId()
        self._loaded = {}
        self._tick = 0
        self._cursor = 0

    def listen(self, system):
        for event, callback in (("ModBlockEntityLoadedClientEvent", self._load),
                                ("ModBlockEntityRemoveClientEvent", self._remove),
                                ("ModBlockEntityTickClientEvent", self._update),
                                ("OnScriptTickClient", self._advance)):
            system.ListenForEvent(self._api.GetEngineNamespace(), self._api.GetEngineSystemName(),
                                  event, self, callback)

    def _key(self, args):
        return args["dimensionId"], (args["posX"], args["posY"], args["posZ"])

    def _load(self, args):
        if args["blockName"] == CHUTE:
            key = self._key(args)
            self._loaded[key] = None
            self._refresh(key)

    def _remove(self, args):
        self._loaded.pop(self._key(args), None)

    def _update(self, args):
        key = self._key(args)
        if key in self._loaded:
            self._refresh(key)

    def _refresh(self, key):
        dim, pos = key
        if self._factory.CreateGame(self._level).GetCurrentDimension() != dim:
            return
        blocks = self._factory.CreateBlockInfo(self._level)
        current = blocks.GetBlock(pos)
        if current is None:
            return
        if current[0] != CHUTE:
            self._loaded.pop(key, None)
            return
        down = current[1] == 0
        if self._loaded[key] != down:
            if blocks.SetBlockEntityMolangValue(pos, "variable.anvilcraft_down", float(down)):
                self._loaded[key] = down

    def _advance(self):
        self._tick += 1
        if self._tick % 15 or not self._loaded:
            return
        keys = sorted(self._loaded)
        for _ in range(min(16, len(keys))):
            self._cursor %= len(keys)
            self._refresh(keys[self._cursor])
            self._cursor += 1
