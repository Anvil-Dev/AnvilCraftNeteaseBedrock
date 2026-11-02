# 来源与许可

本仓库沿用 AnvilCraft 的代码许可和非代码资源许可，并保留两份许可证的原始内容。

| 项目 | 来源与适用方式 |
| --- | --- |
| 上游项目 | [Anvil-Dev/AnvilCraft](https://github.com/Anvil-Dev/AnvilCraft) |
| 本次调研提交 | `ef65f8a876c4d4d695a2f263f3f62d9280e10dad` |
| 代码许可 | [LICENSE](LICENSE)，保留 `Copyright (c) 2024 Gugle`、LGPL 第 3 版和所附 GPL 第 3 版全文；文件头包含后续版本许可选项 |
| 非代码资源许可 | [ASSETS_LICENSE](ASSETS_LICENSE)，原文为 `All rights reserved unless explicitly stated.` |

上游 README 将代码和非代码资产分别指向这两份文件。复制纹理、模型、音效、语言文件等资源时，需要逐项记录来源、作者和适用授权；迁移时制作的新资源也按本仓库资源许可处理，另有说明的文件按其说明处理。

调研文档记录玩法、源码位置和迁移方案。每次实际移植代码或引入资源时，需要记录上游路径、提交与修改内容，以便保留归属信息并跟踪更新。

阶段 0 的方块粉碎沿用上述提交中 `src/generated/resources/data/anvilcraft/recipe/block_crush/gravel.json` 与 `sand.json` 的输入和产物，落地结算按网易事件在 Python 2.7 中重新实现。实验方块引用游戏自带的纹理图集，实验界面的 JSON 与中文名称由本项目编写。

开发依赖 `mc-netease-sdk` 是网易发布的接口补全包，其版权与许可归属该依赖自身；游戏发布包通过网易运行环境调用 ModSDK。
