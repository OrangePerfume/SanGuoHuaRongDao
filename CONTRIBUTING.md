# 贡献与问题反馈

欢迎提交 Issue / PR。请优先报告可稳定复现的问题，附上系统版本、操作步骤、期望与实际结果；若是界面问题，可以附经过脱敏的截图。

建议使用 Python 3.12 x64，在 Windows 10/11 或 CI 对应环境运行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

提交 PR 时不要删除已有测试、跳过失败断言或放宽游戏移动规则。新增移动方式应先完成状态/碰撞/撤销测试。请勿提交 `dist/`、`build/`、`.venv/`、含私人数据的日志或不具备分发授权的图片。
