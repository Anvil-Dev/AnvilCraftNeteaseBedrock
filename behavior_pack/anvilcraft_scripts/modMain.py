# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""通过网易 ModSDK 注册铁砧加工；客户端保留原版铁砧界面。"""

from mod.common.mod import Mod
from mod_log import logger


@Mod.Binding(name="AnvilCraft", version="0.1.0")
class AnvilCraftMod(object):

    @Mod.InitServer()
    def init_server(self):
        import mod.server.extraServerApi as server_api
        server_api.RegisterSystem("AnvilCraft", "Impact",
                                  "anvilcraft_scripts.server.impact.ImpactSystem")

    @Mod.InitClient()
    def init_client(self):
        import mod.client.extraClientApi as client_api
        logger.info("[AnvilCraft] client ready; Minecraft=%s engine=%s",
                    client_api.GetMinecraftVersion(), client_api.GetEngineVersion())
