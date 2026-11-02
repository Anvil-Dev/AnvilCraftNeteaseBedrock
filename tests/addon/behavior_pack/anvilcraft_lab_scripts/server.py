# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""只在测试存档内记录重力事件、读写实验样品并定向回复操作者。"""

import time

import mod.server.extraServerApi as server_api
from mod_log import logger

from anvilcraft_lab_scripts.sample import make_sample, sample_status, within_reach

PROBE = "anvilcraft_lab:probe"
ANVILS = ("minecraft:anvil", "anvilcraft_lab:falling_anvil")
CASES = ("minecraft:chest", "anvilcraft_lab:sample_container")


def _value(data, name):
    try:
        return data[name] or 0
    except KeyError:
        return 0


class LabServer(server_api.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(LabServer, self).__init__(namespace, name)
        self._factory = server_api.GetEngineCompFactory()
        level = server_api.GetLevelId()
        self._blocks = self._factory.CreateBlockInfo(level)
        self._data = self._factory.CreateBlockEntityData(level)
        self._items = self._factory.CreateItem(level)
        self._game = self._factory.CreateGame(level)
        self._sessions = {}
        self._sequence = 0
        for event, callback in (
            ("HeavyBlockStartFallingServerEvent", self._start),
            ("FallingBlockReturnHeavyBlockServerEvent", self._land),
            ("FallingBlockBreakServerEvent", self._break),
            ("BlockStrengthChangedServerEvent", self._signal),
            ("ServerBlockUseEvent", self._open),
            ("DelServerPlayerEvent", self._leave),
        ):
            self.ListenForEvent(server_api.GetEngineNamespace(), server_api.GetEngineSystemName(),
                                event, self, callback)
        self.ListenForEvent("AnvilCraftLab", "Client", "ProbeRequest", self, self._request)
        logger.info("[AnvilCraftLab] server ready; Minecraft=%s", server_api.GetMinecraftVersion())

    def _trace(self, event, name, args, pos):
        if name in ANVILS:
            logger.info("[AnvilCraftLab] fall=%s block=%s dim=%s id=%s pos=%s fallTicks=%s",
                        event, name, args["dimensionId"], args["fallingBlockId"], pos,
                        args.get("fallTickAmount"))

    def _start(self, args):
        self._trace("start", args["blockName"], args, (args["blockX"], args["blockY"], args["blockZ"]))

    def _land(self, args):
        self._trace("land", args["heavyBlockName"], args, (args["blockX"], args["blockY"], args["blockZ"]))

    def _break(self, args):
        self._trace("break", args["blockName"], args,
                    (args["fallingBlockX"], args["fallingBlockY"], args["fallingBlockZ"]))

    def _signal(self, args):
        if args["blockName"] != PROBE:
            return
        pos = (args["posX"], args["posY"], args["posZ"])
        data = self._data.GetBlockEntityData(args["dimensionId"], pos)
        if data is not None:
            data["last_signal"] = args["newStrength"]
            data["signal_changes"] = _value(data, "signal_changes") + 1
        logger.info("[AnvilCraftLab] redstone dim=%s pos=%s old=%s new=%s",
                    args["dimensionId"], pos, args["oldStrength"], args["newStrength"])

    def _open(self, args):
        if args["blockName"] != PROBE:
            return
        player = args["playerId"]
        pos = (args["x"], args["y"], args["z"])
        dim = args["dimensionId"]
        now = time.time()
        previous = self._sessions.get(player)
        if previous and (dim, pos) == previous[:2] and now - previous[3] < 1:
            return
        if not self._can_use(player, dim, pos):
            return
        self._sequence += 1
        self._sessions[player] = (dim, pos, self._sequence, now, 0)
        self.NotifyToClient(player, "ProbeOpen", {"token": self._sequence})

    def _can_use(self, player, dim, pos):
        if self._factory.CreateDimension(player).GetEntityDimensionId() != dim:
            return False
        if not within_reach(self._factory.CreatePos(player).GetFootPos(), pos):
            return False
        return (self._blocks.GetBlockNew(pos, dim) or {}).get("name") == PROBE

    def _request(self, args):
        # __id__ 由引擎附加；坐标、维度与附近容器均从服务端交互记录推导。
        player = args["__id__"]
        session = self._sessions.get(player)
        if session is None or args.get("token") != session[2]:
            return
        dim, pos, token, opened, last = session
        now = time.time()
        if now - opened > 120 or not self._can_use(player, dim, pos):
            del self._sessions[player]
            self.NotifyToClient(player, "ProbeResult", {"token": token, "text": u"请重新点击附近的检测台。"})
            return
        action = args.get("action")
        if now - last < 0.25 or action not in ("read", "sample"):
            return
        self._sessions[player] = (dim, pos, token, opened, now)
        message = self._inspect(player, dim, pos, action)
        self.NotifyToClient(player, "ProbeResult", {"token": token, "text": message})

    def _inspect(self, player, dim, pos, action):
        data = self._data.GetBlockEntityData(dim, pos)
        if data is None:
            return u"无法读取检测台方块实体。"
        status = u"红石：{0}　变化次数：{1}".format(_value(data, "last_signal"), _value(data, "signal_changes"))
        case = (pos[0] + 1, pos[1], pos[2])
        name = (self._blocks.GetBlockNew(case, dim) or {}).get("name")
        if name not in CASES:
            return status + u"\n请在检测台东侧紧贴放置箱子或实验样品箱。"
        size = self._items.GetContainerSize(case, dim)
        # 面板固定测试 0 号槽，不接受客户端提供的槽位或物品字典。
        if not size or size < 1:
            return status + u"\n引擎未返回可用槽位。"
        item = self._items.GetContainerItem(case, 0, dim, True)
        if action == "sample":
            if self._game.GetPlayerGameType(player) != 1:
                return status + u"\n只有创造模式可写入实验样品。"
            if item and item.get("count", 0):
                return status + u"\n第 1 格非空，已保留原物品。"
            if not self._items.SpawnItemToContainer(make_sample(), 0, case, dim):
                return status + u"\n引擎拒绝写入样品。"
            item = self._items.GetContainerItem(case, 0, dim, True)
        return status + u"\n容器：{0} 格　第 1 格：{1}".format(size, sample_status(item))

    def _leave(self, args):
        self._sessions.pop(args["id"], None)
