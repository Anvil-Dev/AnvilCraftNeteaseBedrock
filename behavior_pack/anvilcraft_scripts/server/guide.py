# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""按上游首次进入世界的奖励发放手册，使用网易书本界面阅读。"""

import mod.server.extraServerApi as server_api
from mod_log import logger


class GuideSystem(server_api.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(GuideSystem, self).__init__(namespace, name)
        self.ListenForEvent(server_api.GetEngineNamespace(), server_api.GetEngineSystemName(),
                            "ClientLoadAddonsFinishServerEvent", self, self._give_book)

    def _give_book(self, args):
        player = args["playerId"]
        factory = server_api.GetEngineCompFactory()
        data = factory.CreateExtraData(player)
        key = "anvilcraft:guide_received"
        if data.GetExtraData(key):
            return
        if not data.SetExtraData(key, True):
            logger.warning("[AnvilCraft] could not record guide reward for %s", player)
            return
        book = {"newItemName": "anvilcraft:guide_book", "newAuxValue": 0, "count": 1}
        if factory.CreateItem(player).SpawnItemToPlayerInv(book, player):
            return
        pos = factory.CreatePos(player).GetFootPos()
        dim = factory.CreateDimension(player).GetEntityDimensionId()
        if pos is not None:
            entity = self.CreateEngineItemEntity(book, dim, pos)
            if entity not in (None, False, "", "-1", -1):
                return
        if not data.SetExtraData(key, False):
            logger.error("[AnvilCraft] could not release undelivered guide reward for %s", player)
        else:
            logger.warning("[AnvilCraft] guide delivery deferred until next join for %s", player)
