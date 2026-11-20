[简体中文](README.md) · [繁體中文](docs/zh-TW/README.md) · [English](docs/en/README.md)

# 三国华容道 · 横刀立马（V0.2.0）

[![Windows CI](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml/badge.svg)](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml) [![MIT License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

一款面向 **Windows 10 / 11** 的完全离线单机华容道游戏：保留经典「横刀立马」玩法，采用彩色木质棋盘与三国人物插画。怀旧的是玩法，而不是黑白屏幕。

**版本：0.2.0**。本版在 V0.1.0 基础上新增点击移动及同向多选。

![项目素材生成的静态预览，不是 Windows 实机截图](PREVIEW.png)

> 上图为项目素材静态预览，不代表 Windows 实际渲染效果。程序界面语言仍为简体中文；这里提供的是三种语言的**项目文档**。

## 游戏规则

- 棋盘为 **4 列 × 5 行**，包含 10 枚棋子与两个空位。
- 曹操占 **2×2**，关羽占 **2×1**，四名竖将各占 **1×2**，四名小兵各占 **1×1**。
- 棋子只能沿水平或垂直方向滑动；不可旋转、跨越、重叠或越界。
- 将曹操移动到棋盘**底部中央出口**即可通关。

## 操作说明

- **鼠标拖动**：按住一枚棋子沿水平或垂直方向拖动；路径必须逐格合法。
- **键盘**：单击选中棋子后使用方向键或 WASD，每次移动一格。
- **快捷键**：Ctrl+Z 撤销、R 重开、空格暂停 / 继续。
- **计步与计时**：每枚棋子每移动一格记一步；第一次有效移动启动计时；完成后保存本地最佳成绩。
- **点击移动**：单击棋子，再点击可达的绿色目标空位，沿合法直线自动移动；成功后清除选中和目标提示。
- **Ctrl 多选**：按住 Ctrl 依次点击棋子，多枚棋子可沿相同方向、相同距离一起移动；任一棋子碰撞或越界则不允许该次移动。
- **完整目标提示**：曹操显示一个 2×2 正方形、横将一个 2×1 横长方形、竖将一个 1×2 竖长方形、小兵一个 1×1 正方形，不拆成小格。
- **整组撤销**：多选的一次整体移动可一次撤销；步数仍按棋子数量 × 移动格数计算。

- **玩法提示排版**：右侧提示区分组展示操作说明，自动换行；窗口较小时可在提示区内滚动查看全部内容。

## 下载与运行

从 [GitHub Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases) 下载与版本匹配的 `SanGuoHuaRongDao-v0.2.0-win-x64.zip`（仅在构建及发布成功后可用）。完整解压后运行：

`SanGuoHuaRongDao/SanGuoHuaRongDao.exe`

不要单独复制 EXE，需保留同目录的依赖文件。游戏运行无需联网。

## 源码运行 / Windows 构建

建议 Python 3.12 x64。在项目根目录运行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

双击 `build.cmd` 可安装构建依赖、运行完整测试并生成 `dist\SanGuoHuaRongDao\SanGuoHuaRongDao.exe`。首次安装依赖需要联网。

## 项目结构与质量

| 路径 | 功能 |
| --- | --- |
| `huarongdao/core.py` | 棋局规则、碰撞检测、求解器 |
| `huarongdao/model.py` | 游戏状态、撤销、计时、计步 |
| `huarongdao/gui.py` | PySide6 / Qt 界面 |
| `huarongdao/records.py` | 本地成绩记录 |
| `huarongdao/assets/` | 人物插画、棋盘纹理和图标 |
| `tests/` | 逻辑、资源、UI 烟雾测试及文档一致性测试 |
| `.github/workflows/` | Windows CI 与标签发布 |

测试门禁：`python -m unittest discover -s tests -v`。CI 在 Windows 安装 Qt 后运行；仅通过无 Qt 环境的测试不等于完成实际 Windows GUI 验收。

## 开源许可与其他文档

项目许可见 [LICENSE](LICENSE)（MIT）；Qt/PySide6 及构建依赖的许可说明见 [第三方组件声明](THIRD_PARTY_NOTICES.md)。人物插画为 AI 辅助创作的项目素材，未使用影视或其他游戏的现成截图。

[更新记录](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md) · [第三方组件声明](THIRD_PARTY_NOTICES.md) · [发布列表](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases)
