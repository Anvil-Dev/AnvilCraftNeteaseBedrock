# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""将实验系统注册在独立命名空间，正式包不依赖这些脚本。"""

from mod.common.mod import Mod


@Mod.Binding(name="AnvilCraftLab", version="0.1.4")
class LabMod(object):

    @Mod.InitServer()
    def init_server(self):
        import mod.server.extraServerApi as server_api
        server_api.RegisterSystem("AnvilCraftLab", "Server", "anvilcraft_lab_scripts.server.LabServer")

    @Mod.InitClient()
    def init_client(self):
        import mod.client.extraClientApi as client_api
        client_api.RegisterSystem("AnvilCraftLab", "Client", "anvilcraft_lab_scripts.client.LabClient")
