# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""在网易服务端注册铁砧落地监听。"""

import mod.server.extraServerApi as server_api
from mod_log import logger

from anvilcraft_scripts.server.impact_events import ImpactEvents


class ImpactSystem(server_api.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(ImpactSystem, self).__init__(namespace, name)
        self._events = ImpactEvents(server_api, logger)
        self._events.listen(self)
        logger.info("[AnvilCraft] server ready; Minecraft=%s", server_api.GetMinecraftVersion())
