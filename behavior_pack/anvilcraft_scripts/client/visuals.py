# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""在网易客户端注册机器模型的方向同步。"""

import mod.client.extraClientApi as client_api

from anvilcraft_scripts.client.visual_events import VisualEvents


class VisualsSystem(client_api.GetClientSystemCls()):

    def __init__(self, namespace, name):
        super(VisualsSystem, self).__init__(namespace, name)
        self._events = VisualEvents(client_api)
        self._events.listen(self)

    def Destroy(self):
        self.UnListenAllEvents()
