[简体中文](README.md) · [繁體中文](docs/zh-TW/README.md) · [English](docs/en/README.md)

# 三国华容道 · 横刀立马（V0.5.0）

[![Windows CI](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml/badge.svg)](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml) [![MIT License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

一款面向 **Windows 10 / 11** 的完全离线单机华容道游戏：保留经典「横刀立马」玩法，采用彩色木质棋盘与三国人物插画。怀旧的是玩法，而不是黑白屏幕。

**版本：0.5.0**。优化棋子动画交互，修复通关提示竞态与键盘焦点导航问题。

![项目素材生成的静态预览，不是 Windows 实机截图](PREVIEW.png)

> 上图为项目素材静态预览。程序界面和项目文档均支持简体中文、繁体中文与英文；只需一套 EXE，即可切换三种界面语言。

## 界面语言

- 通过游戏窗口右上角的 **「语言 / Language」按钮**，选择 **简体中文 / 繁體中文 / English**。
- 切换立即生效，包括棋盘、人物姓名、按钮、玩法说明、成绩和弹窗；不需要重新启动。
- 默认简体中文；自动记住上次选择。切换语言不会清除当前棋局、移动记录、计时或动画速度。

## 游戏规则

- 棋盘为 **4 列 × 5 行**，包含 10 枚棋子与两个空位。
- 曹操占 **2×2**，关羽占 **2×1**，四名竖将各占 **1×2**，四名小兵各占 **1×1**。
- 棋子只能沿水平或垂直方向滑动；不可旋转、跨越、重叠或越界。
- 将曹操移动到棋盘**底部中央出口**即可通关。

## 操作说明

- **鼠标拖动**：按住一枚棋子沿水平或垂直方向拖动；路径必须逐格合法。
- **键盘**：单击或使用 Q / E 选中棋子，方向键或 WASD 每次移动一格；Tab / Shift+Tab 切换界面焦点。
- **快捷键**：Ctrl+Z 撤销、R 重开、空格暂停 / 继续。
- **计步与计时**：每枚棋子每移动一格记一步；第一次有效移动启动计时；完成后保存本地最佳成绩。
- **点击移动**：单击棋子，再点击可达的绿色目标空位，沿合法直线自动移动；成功后清除选中和目标提示。
- **Ctrl 多选**：按住 Ctrl 依次点击棋子，多枚棋子可沿相同方向、相同距离一起移动；任一棋子碰撞或越界则不允许该次移动。
- **完整目标提示**：曹操显示一个 2×2 正方形、横将一个 2×1 横长方形、竖将一个 1×2 竖长方形、小兵一个 1×1 正方形，不拆成小格。
- 合并同方向重叠的移动预选框，统一描边和填充，保留各合法移动距离。
- **整组撤销**：多选的一次整体移动可一次撤销；步数仍按棋子数量 × 移动格数计算。

- **棋子滑动动画**：快速连续操作时，从棋子当前显示位置接续滑动；撤销动作也平滑回退。
- **滑动速度**：右侧操作区提供慢、标准、快三档，自动保存选择，下次启动继续生效。
- **玩法提示排版**：右侧提示区分组展示操作说明，自动换行；窗口较小时可在提示区内滚动查看全部内容。

## 下载与运行

从 [GitHub Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases) 下载与版本匹配的 `SanGuoHuaRongDao-v0.5.0-win-x64.zip`。完整解压后运行：

`SanGuoHuaRongDao.exe`

EXE 内置运行资源，无需单独安装 Python 或 Qt。游戏无需联网。请保留 README.md 和 LICENSE.txt。

Windows 发布改用单文件 EXE，ZIP 仅包含程序、README.md 与合并许可声明 LICENSE.txt。

## 源码运行 / Windows 构建

建议 Python 3.12 x64。在项目根目录运行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

双击 `build.cmd` 可安装构建依赖、运行完整测试并生成 `dist\SanGuoHuaRongDao.exe`。首次安装依赖需要联网。构建完成后自动显示 EXE 文件、完整发布目录的实测体积；自动发布流程还会统计 ZIP 大小。

## 项目结构与质量

| 路径 | 功能 |
| --- | --- |
| `huarongdao/core.py` | 棋局规则、碰撞检测、求解器 |
| `huarongdao/model.py` | 游戏状态、撤销、计时、计步 |
| `huarongdao/gui.py` | PySide6 / Qt 界面 |
| `huarongdao/i18n.py` | 简体中文、繁体中文、英文界面翻译 |
| `huarongdao/records.py` | 本地成绩记录 |
| `huarongdao/assets/` | 人物插画、棋盘纹理和图标 |
| `tests/` | 逻辑、资源、UI 烟雾测试及文档一致性测试 |
| `.github/workflows/` | Windows CI 与标签发布 |

严格测试门禁：`python -X faulthandler tools/run_tests.py --require-qt`。Windows CI 覆盖游戏规则与 Qt 图形界面，门禁失败时停止构建。

## 开源许可与其他文档

项目许可见 [LICENSE](LICENSE)（MIT）；Qt/PySide6 及构建依赖的许可说明见 [第三方组件声明](THIRD_PARTY_NOTICES.md)。人物插画为 AI 辅助创作的项目素材，未使用影视或其他游戏的现成截图。

[更新记录](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md) · [第三方组件声明](THIRD_PARTY_NOTICES.md) · [发布列表](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases)
