"""三国华容道 Windows EXE 入口。"""
import sys
from huarongdao.gui import run


def smoke_test() -> int:
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from shiboken6 import delete
    from huarongdao.gui import ASSETS, PORTRAITS, MainWindow

    app = QApplication([])
    window = None
    try:
        for path in [ASSETS / 'wood_board.jpg', ASSETS / 'wood_dark.jpg',
                     *(ASSETS / 'portraits' / f'{name}.png' for name in set(PORTRAITS))]:
            if QPixmap(str(path)).isNull():
                raise RuntimeError(f'Bundled resource missing: {path}')
        window = MainWindow()
        window.resize(1170, 840)
        window.show()
        app.processEvents()
        for language in ('zh-CN', 'zh-TW', 'en'):
            window.set_language(language, persist=False)
            app.processEvents()
            if window.grab().isNull():
                raise RuntimeError(f'Window render failed: {language}')
        return 0
    finally:
        if window is not None:
            window.close()
            delete(window)
        app.processEvents()
        delete(app)


if __name__ == '__main__':
    raise SystemExit(smoke_test() if sys.argv[1:] == ['--smoke-test'] else run())
