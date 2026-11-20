[简体中文](../../CONTRIBUTING.md) · [繁體中文](../../docs/zh-TW/CONTRIBUTING.md) · [English](../../docs/en/CONTRIBUTING.md)

# 貢獻指南與問題回報

歡迎透過 GitHub Issues 回報錯誤，或使用 Pull Requests 提交修正與功能強化。請提供 Windows 版本、重現步驟、實際與預期結果；介面問題可附上已遮蔽敏感資訊的截圖。

## 開發與驗證

建議 Python 3.12 x64，執行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

## 提交原則

- PR 請清楚說明變更範圍、風險與測試結果。
- 新增移動方式時，須測試邊界、碰撞、復原、步數與過關判定；不得刪除既有測試或略過失敗的斷言。
- 更新 README、更新紀錄或發行說明時，同步維護簡體中文、繁體中文及英文文件。
- 請勿提交 `dist/`、`build/`、`.venv/`、私人日誌、金鑰或未取得散布授權的素材。
- GUI 測試須在安裝 PySide6 的 Windows 環境執行；純 Python 測試並不等同 Windows EXE 驗收。

授權條款請見 [LICENSE](../../LICENSE)；相依套件與素材資訊見 [第三方元件聲明](THIRD_PARTY_NOTICES.md)。
