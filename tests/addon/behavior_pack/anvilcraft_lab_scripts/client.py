# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""用同一套触屏与鼠标控件查看服务端返回的实验结果。"""

import mod.client.extraClientApi as client_api
from mod_log import logger


class LabClient(client_api.GetClientSystemCls()):

    def __init__(self, namespace, name):
        super(LabClient, self).__init__(namespace, name)
        self.panel = None
        self.token = None
        self._ready = False
        self.ListenForEvent(client_api.GetEngineNamespace(), client_api.GetEngineSystemName(),
                            "UiInitFinished", self, self._init_ui)
        self.ListenForEvent("AnvilCraftLab", "Server", "ProbeOpen", self, self._open)
        self.ListenForEvent("AnvilCraftLab", "Server", "ProbeResult", self, self._result)

    def _init_ui(self, args):
        client_api.RegisterUI("AnvilCraftLab", "Probe", "anvilcraft_lab_scripts.client.ProbeScreen",
                              "anvilcraft_lab_probe.main")
        self._ready = True
        logger.info("[AnvilCraftLab] UI ready; engine=%s", client_api.GetEngineVersion())

    def _open(self, args):
        if not self._ready:
            return
        self.token = args["token"]
        if self.panel is None:
            client_api.PushScreen("AnvilCraftLab", "Probe")
        self.request("read")

    def request(self, action):
        self.NotifyToServer("ProbeRequest", {"token": self.token, "action": action})

    def _result(self, args):
        if self.panel and self.token == args["token"]:
            game = client_api.GetEngineCompFactory().CreateGame(client_api.GetLevelId())
            self.panel.show_status(u"{0}\n客户端：{1} FPS".format(args["text"], game.GetFps()))


class ProbeScreen(client_api.GetScreenNodeCls()):

    def Create(self):
        self._client = client_api.GetSystem("AnvilCraftLab", "Client")
        self._client.panel = self
        for name, callback in (("read", self._read), ("sample", self._sample), ("close", self._close)):
            control = self.GetBaseUIControl("/panel/" + name).asButton()
            control.AddTouchEventParams({"isSwallow": True})
            control.SetButtonTouchUpCallback(callback)

    def show_status(self, message):
        self.GetBaseUIControl("/panel/status").asLabel().SetText(message)

    def _read(self, args):
        self._client.request("read")

    def _sample(self, args):
        self._client.request("sample")

    def _close(self, args):
        client_api.PopScreen()

    def Destroy(self):
        self._client.panel = None
