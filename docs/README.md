# 开发者文档索引

本目录存放铁砧工艺网易基岩版的开发规范、上游特性迁移方案、阶段计划与源码统计数据。

## 技术基线

| 项目 | 当前配置 |
| --- | --- |
| 运行与脚本语言 | Python `2.7.18`（见 [`.python-version`](../.python-version)） |
| 目标引擎与 ModSDK | 基岩引擎 `1.21.130`、网易 ModSDK `3.10`、补全包 `mc-netease-sdk==3.10.0.81573`（见 [`requirements-dev.txt`](../requirements-dev.txt)） |
| 对照上游仓库 | [Anvil-Dev/AnvilCraft](https://github.com/Anvil-Dev/AnvilCraft) |
| 对照分支与提交 | `dev/1.21/1.6`，`ef65f8a876c4d4d695a2f263f3f62d9280e10dad`（模组版本 `1.6.0`） |
| 调研与统计日期 | 2026-11-02 |
| 当前代码状态 | 当前开发代码已接入 246 条原版落砧配方和游戏内手册，包含双方块压合、炼药锅方块压榨、脚手架筛分和方块涂抹。圆石粉碎链已通过网易 3.10 PC 实测，其余配方已在 Python 2.7 验证，待游戏内验收 |

## 文档列表

| 文档 | 内容说明 |
| --- | --- |
| [development.md](development.md) | Python 2.7 环境配置、目标包目录结构、脚本编写规范与本地检查命令 |
| [recipes.md](recipes.md) | 主包已接入的生存配方、加工平台、基岩版 ID 映射与验收记录 |
| [migration-research.md](migration-research.md) | 上游玩法在网易 ModSDK 下的实现方案、API 限制与数据映射规则 |
| [development-plan.md](development-plan.md) | 阶段 0 至阶段 6 的开发任务、前置依赖与游戏内验收标准 |
| [sources.md](sources.md) | 上游 Java 源码入口索引、网易 ModAPI 官方文档链接与配方统计方法 |
| [source-inventory.json](source-inventory.json) | 上游 1,628 个静态配方文件的分类计数与许可证文件 SHA-256 摘要 |

## 常用开发命令

在仓库根目录使用 Python 2.7 安装补全依赖并运行静态检查：

```powershell
python -m pip install -r requirements-dev.txt
python tools/check.py
```
