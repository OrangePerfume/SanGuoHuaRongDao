[简体中文](CONTRIBUTING.md) · [繁體中文](docs/zh-TW/CONTRIBUTING.md) · [English](docs/en/CONTRIBUTING.md)

# 贡献指南与问题反馈

欢迎通过 GitHub Issues 报告缺陷，通过 Pull Requests 提交修复和功能增强。问题报告请说明 Windows 版本、复现步骤、实际结果与预期结果；界面问题可附去除敏感信息后的截图。

## 开发与验证

建议使用 Python 3.12 x64，运行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

## 提交要求

- 尽量保持提交范围明确，并在 PR 中说明改动、风险和测试结果。
- 新增移动模式时，必须覆盖边界、碰撞、撤销、计步与胜利判定；不得删减现有测试或跳过失败断言。
- 修改 README、更新日志或发布说明时，同步更新简体中文、繁体中文与英文文档。
- 不提交 `dist/`、`build/`、`.venv/`、私密日志、密钥或未经授权的第三方素材。
- GUI 测试应在安装 PySide6 的 Windows 环境下执行；本地纯 Python 测试并不等同于 Windows EXE 验收。

## 界面翻译

- 修改游戏界面文字时，同步维护 `huarongdao/i18n.py` 内的简体、繁体和英文翻译，并检查语言切换后的界面显示。

完整授权条件参见 [LICENSE](LICENSE)，依赖与资源声明见 [第三方组件声明](THIRD_PARTY_NOTICES.md)。
