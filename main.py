"""三国华容道 Windows EXE 入口。"""
import sys
from huarongdao.gui import run


def smoke_test() -> int:
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from shiboken6 import delete
    from huarongdao.gui import ASSETS, PORTRAITS, MainWindow
    from huarongdao.hint import format_hint

    app = QApplication([])
    window = None
    try:
        for path in [ASSETS / 'wood_board.jpg', ASSETS / 'wood_dark.jpg', ASSETS / 'red_cliffs.jpg',
                     *(ASSETS / 'portraits' / f'{name}.png' for name in set(PORTRAITS))]:
            if QPixmap(str(path)).isNull():
                raise RuntimeError(f'Bundled resource missing: {path}')
        window = MainWindow()
        window.resize(1170, 840)
        window.show()
        app.processEvents()
        window.hint_button.click()
        hint = window.board.solution_hint
        if hint is None or window.game.steps or window.game.running:
            raise RuntimeError('Next-move hint failed or modified the puzzle')
        for language in ('zh-CN', 'zh-TW', 'en'):
            window.set_language(language, persist=False)
            if (window.board.solution_hint != hint
                    or window.hint_message.text() != format_hint(language, hint)):
                raise RuntimeError(f'Hint translation failed: {language}')
            window.set_help_expanded(True)
            for width, height in ((990, 700), (1170, 840)):
                window.resize(width, height)
                app.processEvents()
                if window.grab().isNull():
                    raise RuntimeError(f'Window render failed: {language} {width}x{height}')
                if not window.board.rect().contains(window.selected_info.geometry()):
                    raise RuntimeError(f'Selection plaque outside board area: {language}')
                for scroll in (window.side_scroll, window.help_scroll):
                    if (scroll.horizontalScrollBar().maximum() != 0
                            or scroll.widget().width() > scroll.viewport().width()):
                        raise RuntimeError(f'Horizontal overflow: {language} {width}x{height} {scroll.objectName()}')
        window.clear_hint_button.click()
        if window.board.solution_hint is not None:
            raise RuntimeError('Next-move hint did not clear')
        return 0
    finally:
        if window is not None:
            window.close()
            delete(window)
        app.processEvents()
        delete(app)


if __name__ == '__main__':
    raise SystemExit(smoke_test() if sys.argv[1:] == ['--smoke-test'] else run())
