"""三国华容道桌面界面：彩色木纹棋盘与人物画像。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal,
    QSettings, QSignalBlocker, QStandardPaths,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QKeySequence, QLinearGradient,
    QAction, QActionGroup, QPainter, QPainterPath, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QMenu, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .core import BOARD_W, PIECES, display_hint_rectangles, occupied_by, shifted_group, target_for_click
from .model import GameModel
from .motion import ANIMATION_DURATIONS_MS, MotionTrack
from .records import RecordStore
from .i18n import LANGUAGES, HELP_IDS, DEFAULT_LANGUAGE, normalize_language, piece_name, selected_names, tr

ASSETS = Path(__file__).resolve().parent / "assets"
PORTRAITS = [
    "caocao", "guanyu", "zhangfei", "zhaoyun", "machao", "huangzhong",
    "soldier", "soldier", "soldier", "soldier",
]
BORDERS = [
    "#E8B468", "#CBA36E", "#CF8C59", "#82B6C9", "#79A8D0", "#C9A15F",
    "#AE9B80", "#AE9B80", "#AE9B80", "#AE9B80",
]
TINTS = [
    "#A93A33", "#426B4D", "#8D4D34", "#477A9A", "#456986", "#8F6B33",
    "#71533C", "#71533C", "#71533C", "#71533C",
]


def c(hexcode: str, alpha: int | None = None) -> QColor:
    color = QColor(hexcode)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def font(point: int, bold: bool = False, serif: bool = False) -> QFont:
    f = QFont("Microsoft YaHei UI" if not serif else "Microsoft YaHei", point)
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def image_fill(painter: QPainter, pixmap: QPixmap, dest: QRectF, bias_y: float = 0.5) -> None:
    if pixmap.isNull() or dest.isEmpty():
        return
    source_w, source_h = pixmap.width(), pixmap.height()
    target_aspect = dest.width() / dest.height()
    source_aspect = source_w / source_h
    if source_aspect >= target_aspect:
        crop_width = source_h * target_aspect
        source = QRectF((source_w - crop_width) / 2, 0, crop_width, source_h)
    else:
        crop_height = source_w / target_aspect
        source = QRectF(0, (source_h - crop_height) * bias_y, source_w, crop_height)
    painter.drawPixmap(dest, pixmap, source)


class BoardWidget(QWidget):
    move_requested = Signal(int, int, int, int)
    group_move_requested = Signal(object, int, int, int)
    selection_changed = Signal(str)

    def __init__(self, game: GameModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.game = game
        self.language = DEFAULT_LANGUAGE
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(500, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._images = [QPixmap(str(ASSETS / "portraits" / f"{name}.png")) for name in PORTRAITS]
        self._board = QPixmap(str(ASSETS / "wood_board.jpg"))
        self._dark = QPixmap(str(ASSETS / "wood_dark.jpg"))
        self._selected: set[int] = set()
        # 仅在主动选择目标时显示绿色完整棋子落点；移动成功后不再残留。
        self._targets_visible = False
        self._pressed_pos: QPointF | None = None
        self._pressed_index: int | None = None
        self._preview: dict[int, int] | None = None
        self._motion = MotionTrack()
        self._speed = "normal"
        self._animation = QVariantAnimation(self)
        # Qt requires explicit interpolation endpoints; without them the
        # valueChanged signal need not fire for the intended 0..1 transition.
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(ANIMATION_DURATIONS_MS[self._speed])
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._frame)
        self._animation.finished.connect(self._end_animation)

    def sizeHint(self) -> QSize:
        return QSize(660, 735)

    def _layout(self) -> tuple[float, float, float]:
        # 棋盘主体为 4×5；保留上方标题和下方出口铭牌。
        side = min((self.width() - 96) / 4, (self.height() - 142) / 5)
        side = max(55.0, side)
        left = (self.width() - side * 4) / 2
        top = (self.height() - side * 5) / 2 + 6
        return left, top, side

    def _piece_rect(self, index: int, positions: tuple[int, ...] | None = None) -> QRectF:
        pos = (positions or self.game.positions)[index]
        x0, y0, unit = self._layout()
        piece = PIECES[index]
        x, y = pos % BOARD_W, pos // BOARD_W
        return QRectF(x0 + x * unit + 3, y0 + y * unit + 3,
                      piece.w * unit - 6, piece.h * unit - 6)

    def _hint_rects(self) -> tuple[QRectF, ...]:
        """同方向重叠终点合并为连续矩形，不重复描边或填充。"""
        if not self._selected or not self._targets_visible or self.game.paused or self.game.finished:
            return ()
        x0, y0, unit = self._layout()
        return tuple(
            QRectF(x0 + cx * unit + 7, y0 + cy * unit + 7,
                   width * unit - 14, height * unit - 14)
            for cx, cy, width, height in display_hint_rectangles(
                self.game.positions, tuple(sorted(self._selected))
            )
        )

    def _at(self, point: QPointF) -> int | None:
        x0, y0, unit = self._layout()
        cx = math.floor((point.x() - x0) / unit)
        cy = math.floor((point.y() - y0) / unit)
        return occupied_by(self.game.positions, cx, cy)

    @property
    def animation_duration_ms(self) -> int:
        return ANIMATION_DURATIONS_MS[self._speed]

    def set_animation_speed(self, speed: str) -> None:
        if speed not in ANIMATION_DURATIONS_MS:
            raise ValueError(f"unsupported animation speed: {speed}")
        # Changing preferences during motion must not cause an instantaneous
        # progress jump.  The current frame is the new start of the animation.
        moving = bool(self._motion.starts) and self._motion.progress < 1.0
        if moving:
            before = {i: self.game.positions[i] for i in self._motion.starts}
            self._motion.retarget(before, self.game.positions)
            self._animation.stop()
        self._speed = speed
        self._animation.setDuration(self.animation_duration_ms)
        if moving and self._motion.starts:
            self._animation.start()
        self.update()

    def _frame(self, value: object) -> None:
        self._motion.set_progress(float(value))
        self.update()

    def _end_animation(self) -> None:
        self._motion.complete()
        self.update()

    def animate(self, index: int, original_pos: int) -> None:
        self.animate_group({index: original_pos})

    def animate_group(self, original_positions: dict[int, int]) -> None:
        active = self._motion.retarget(original_positions, self.game.positions)
        self._animation.stop()
        if active:
            self._animation.start()
        self.update()

    def clear_animation(self) -> None:
        self._animation.stop()
        self._motion.complete()
        self._pressed_index = None
        self._pressed_pos = None
        self._preview = None
        self.update()

    def clear_selection(self) -> None:
        self._selected.clear()
        self._emit_selection()

    def hide_targets(self) -> None:
        """成功移动后关闭落点提示；键盘操作仍可保留当前棋子选择。"""
        self._targets_visible = False
        self.update()

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)
        # A language change must not reopen hints hidden by keyboard movement.
        self.selection_changed.emit(selected_names(self.language, tuple(sorted(self._selected))))
        self.update()

    def _emit_selection(self) -> None:
        self._targets_visible = bool(self._selected)
        self.selection_changed.emit(selected_names(self.language, tuple(sorted(self._selected))))
        self.update()

    def _request_move(self, dx: int, dy: int, count: int) -> None:
        indices = tuple(sorted(self._selected))
        if len(indices) == 1:
            self.move_requested.emit(indices[0], dx, dy, count)
        elif len(indices) > 1:
            self.group_move_requested.emit(indices, dx, dy, count)

    def _draw_piece(self, painter: QPainter, i: int, rect: QRectF, selected: bool = False) -> None:
        painter.save()
        shadow = QRectF(rect).translated(1.7, 3.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c("#0E0805", 120))
        painter.drawRoundedRect(shadow, 9, 9)
        painter.setBrush(c(BORDERS[i] if selected else "#39241A"))
        painter.setPen(QPen(c("#25150C"), 1.2))
        painter.drawRoundedRect(rect, 8, 8)
        interior = rect.adjusted(4, 4, -4, -4)
        path = QPainterPath()
        path.addRoundedRect(interior, 5, 5)
        painter.setClipPath(path)
        painter.fillRect(interior, c(TINTS[i]))
        art_height = max(18, interior.height() - min(33, interior.height() * 0.31))
        art_rect = QRectF(interior.left(), interior.top(), interior.width(), art_height + 6)
        image_fill(painter, self._images[i], art_rect, bias_y=0.31 if PIECES[i].h == 1 else 0.47)
        # 顶部暖光，底部姓名牌更清晰。
        sunlight = QLinearGradient(art_rect.topLeft(), art_rect.bottomLeft())
        sunlight.setColorAt(0, c("#F6D6A0", 35))
        sunlight.setColorAt(1, c(TINTS[i], 95))
        painter.fillRect(art_rect, sunlight)
        tag_h = min(32, max(21, interior.height() * 0.26))
        tag = QRectF(interior.left(), interior.bottom()-tag_h, interior.width(), tag_h+1)
        label_grad = QLinearGradient(tag.topLeft(), tag.bottomLeft())
        label_grad.setColorAt(0, c("#3C2318", 218))
        label_grad.setColorAt(1, c("#21130D", 253))
        painter.fillRect(tag, label_grad)
        painter.setPen(QPen(c("#E8BE73", 155), 1))
        painter.drawLine(tag.topLeft(), tag.topRight())
        painter.setPen(c("#F9E4B8"))
        label_size = 11 if PIECES[i].w == 1 else 16
        if PIECES[i].w == 1 and PIECES[i].h == 1:
            label_size = 12
        name = piece_name(self.language, i, tile=True)
        painter.setFont(font(label_size, True))
        # English labels may be longer than CJK names. Fit the wooden nameplate
        # rather than clipping a general's name or creating a second text row.
        while painter.fontMetrics().horizontalAdvance(name) > tag.width() - 7 and label_size > 8:
            label_size -= 1
            painter.setFont(font(label_size, True))
        painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, name)
        painter.setClipping(False)
        # 细致的金属内框（选中时发亮）
        painter.setPen(QPen(c("#F3C878" if selected else "#C79656", 230), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(2.1, 2.1, -2.1, -2.1), 7, 7)
        # 选中角标
        if selected:
            painter.setPen(QPen(c("#FFF1B2"), 2.5))
            for sx in [1, -1]:
                for sy in [1, -1]:
                    cx = rect.left()+8 if sx==1 else rect.right()-8
                    cy = rect.top()+8 if sy==1 else rect.bottom()-8
                    painter.drawLine(QPointF(cx,cy), QPointF(cx+sx*5,cy))
                    painter.drawLine(QPointF(cx,cy), QPointF(cx,cy+sy*5))
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # 整体背景由深木板和边缘光感组成。
        image_fill(painter, self._dark, QRectF(self.rect()))
        painter.fillRect(self.rect(), c("#26170F", 105))
        x0, y0, unit = self._layout()
        frame = QRectF(x0-24, y0-24, unit*4+48, unit*5+48)
        painter.setBrush(c("#120B07", 160))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(frame.translated(5,8), 16,16)
        painter.setBrush(c("#492916"))
        painter.setPen(QPen(c("#DAB06C"), 3))
        painter.drawRoundedRect(frame, 15,15)
        inner_frame = frame.adjusted(11,11,-11,-11)
        painter.setPen(QPen(c("#8D5527"), 3))
        painter.setBrush(c("#3A2114"))
        painter.drawRoundedRect(inner_frame, 7,7)
        board_rect = QRectF(x0,y0,4*unit,5*unit)
        image_fill(painter,self._board,board_rect)
        painter.fillRect(board_rect,c("#3B2110",35))
        painter.setPen(QPen(c("#3C2114", 76), 1))
        for gx in range(1,4):
            px = x0+gx*unit
            painter.drawLine(QPointF(px,y0),QPointF(px,y0+5*unit))
        for gy in range(1,5):
            py = y0+gy*unit
            painter.drawLine(QPointF(x0,py),QPointF(x0+4*unit,py))
        # 上方标题牌
        title_rect = QRectF(x0, max(8,y0-66), unit*4, 31)
        painter.setPen(c("#F1D7A3"))
        painter.setFont(font(15,True))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, tr(self.language, "board_title"))
        # 底部出口：两格宽位置
        exit_rect = QRectF(x0+unit, y0+5*unit+12, 2*unit, 27)
        painter.setBrush(c("#D4A15C"))
        painter.setPen(QPen(c("#72411F"),2))
        painter.drawRoundedRect(exit_rect,5,5)
        painter.setPen(c("#512A17"))
        painter.setFont(font(12,True))
        painter.drawText(exit_rect, Qt.AlignmentFlag.AlignCenter, tr(self.language, "board_exit"))
        # 多选同步动画与多棋子预览；不改变逻辑状态。
        for i in range(len(PIECES)):
            rect = self._piece_rect(i)
            if i in self._motion.starts:
                grid_x, grid_y = self._motion.displayed(i, self.game.positions)
                rect = QRectF(x0 + grid_x * unit + 3, y0 + grid_y * unit + 3,
                              PIECES[i].w * unit - 6, PIECES[i].h * unit - 6)
            if self._preview is not None and i in self._preview:
                ghost = list(self.game.positions)
                ghost[i] = self._preview[i]
                painter.setOpacity(0.30)
                self._draw_piece(painter, i, rect, True)
                painter.setOpacity(1.0)
                rect = self._piece_rect(i, tuple(ghost))
            self._draw_piece(painter, i, rect, i in self._selected)
        # 同方向重叠落点先合并，再统一填充和描边，避免中间颜色加深。
        for hint in self._hint_rects():
            painter.setBrush(c('#8CC786', 65))
            painter.setPen(QPen(c('#D8F0B4', 215), 2.2))
            painter.drawRoundedRect(hint, 9, 9)
        if self.game.paused:
            painter.fillRect(board_rect,c("#120B08",188))
            painter.setPen(c("#F2D6A0"))
            painter.setFont(font(28,True))
            painter.drawText(board_rect, Qt.AlignmentFlag.AlignCenter, tr(self.language, "board_pause"))
        if self.game.finished:
            painter.setBrush(c("#1A3929",228))
            plaque=QRectF(x0+unit*.35,y0+unit*2.15,unit*3.3,unit*.75)
            painter.setPen(QPen(c("#E8CA88"),2))
            painter.drawRoundedRect(plaque,12,12)
            painter.setPen(c("#FFE9B6"))
            painter.setFont(font(20,True))
            painter.setFont(font(14 if self.language == 'en' else 20, True))
            painter.drawText(plaque, Qt.AlignmentFlag.AlignCenter, tr(self.language, "board_win"))
        painter.end()

    def _drag_direction(self, delta: QPointF) -> tuple[int,int,int] | None:
        _,_,unit=self._layout()
        if max(abs(delta.x()),abs(delta.y())) < unit*0.24:
            return None
        if abs(delta.x()) > abs(delta.y()):
            return (1 if delta.x()>0 else -1,0,max(1,round(abs(delta.x())/unit)))
        return (0,1 if delta.y()>0 else -1,max(1,round(abs(delta.y())/unit)))

    def mousePressEvent(self,event) -> None:
        if self.game.paused or self.game.finished:
            return
        self.setFocus()
        if event.button() == Qt.MouseButton.RightButton:
            self.clear_selection()
            self.clear_animation()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self._at(event.position())
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + 点击：逐个加入或移出选择，不影响棋局状态。
            if index is not None:
                if index in self._selected:
                    self._selected.remove(index)
                else:
                    self._selected.add(index)
                self._emit_selection()
            self._pressed_pos = None
            self._pressed_index = None
            self._preview = None
            return
        self._pressed_pos = event.position()
        self._pressed_index = index
        self._preview = None
        if index is not None:
            if index not in self._selected:
                self._selected = {index}
            # 再次点击已选棋子，也应重新显示可达格。
            self._emit_selection()
        self.update()

    def mouseMoveEvent(self,event) -> None:
        if self._pressed_pos is None or self._pressed_index is None or self.game.paused:
            return
        direction = self._drag_direction(event.position()-self._pressed_pos)
        self._preview = None
        if direction is not None:
            dx, dy, count = direction
            indices = tuple(sorted(self._selected))
            candidate = self.game.positions
            for _ in range(count):
                next_state = shifted_group(candidate, indices, dx, dy)
                if next_state is None:
                    break
                candidate = next_state
            if candidate != self.game.positions:
                self._preview = {i: candidate[i] for i in indices}
        self.update()

    def mouseReleaseEvent(self,event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._pressed_pos is None:
            return
        direction = self._drag_direction(event.position() - self._pressed_pos)
        original = self.game.positions
        if self._pressed_index is not None:
            if direction is not None:
                self._request_move(*direction)
            else:
                # 单击已有多选组员，切换回单选；拖动则保留组成员。
                self._selected = {self._pressed_index}
                self._emit_selection()
        elif direction is None and self._selected:
            # 单击空格：将单选/多选棋子自动移动至点击空格。
            x0, y0, unit = self._layout()
            cx = math.floor((event.position().x() - x0)/unit)
            cy = math.floor((event.position().y() - y0)/unit)
            move = target_for_click(self.game.positions, tuple(sorted(self._selected)), cx, cy)
            if move is not None:
                self._request_move(*move)
        # 仅在实际发生位移后取消选择；无效目标不打断操作。
        if self.game.positions != original:
            self.clear_selection()
        self._pressed_pos = None
        self._pressed_index = None
        self._preview = None
        self.update()

    def keyPressEvent(self,event) -> None:
        if self.game.paused or self.game.finished:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.clear_selection()
            event.accept()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            increment = -1 if key == Qt.Key.Key_Backtab else 1
            previous = next(iter(self._selected)) if len(self._selected) == 1 else -1
            self._selected = {(previous + increment) % len(PIECES)}
            self._emit_selection()
            event.accept()
            return
        direction = {
            Qt.Key.Key_Left:(-1,0), Qt.Key.Key_A:(-1,0),
            Qt.Key.Key_Right:(1,0), Qt.Key.Key_D:(1,0),
            Qt.Key.Key_Up:(0,-1), Qt.Key.Key_W:(0,-1),
            Qt.Key.Key_Down:(0,1), Qt.Key.Key_S:(0,1),
        }.get(key)
        if direction and self._selected:
            self._request_move(*direction, 1)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        if not self.game.paused and not self.game.finished:
            increment = 1 if next else -1
            previous = sorted(self._selected)[0] if len(self._selected) == 1 else (-1 if next else 0)
            self._selected = {(previous + increment) % len(PIECES)}
            self._emit_selection()
            return True
        return super().focusNextPrevChild(next)

    def wheelEvent(self,event) -> None:
        # 华容道不使用滚轮移动，以免与系统滚动误操作。
        event.ignore()


class TextureBackground(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._wood=QPixmap(str(ASSETS/'wood_dark.jpg'))

    def paintEvent(self,event) -> None:
        p=QPainter(self)
        image_fill(p,self._wood,QRectF(self.rect()))
        p.fillRect(self.rect(),c('#130C08',100))
        p.end()


class ParchmentPanel(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._parchment=QPixmap(str(ASSETS/'parchment.jpg'))
        self.setObjectName('parchmentPanel')

    def paintEvent(self,event) -> None:
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base=QRectF(self.rect()).adjusted(1,1,-1,-1)
        shape=QPainterPath()
        shape.addRoundedRect(base,13,13)
        p.setClipPath(shape)
        image_fill(p,self._parchment,base)
        p.fillRect(base,c('#EBD6B4',16))
        p.setClipping(False)
        p.setPen(QPen(c('#8B5B33'),3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(base,13,13)
        p.setPen(QPen(c('#C7A375'),1))
        p.drawRoundedRect(base.adjusted(7,7,-7,-7),9,9)
        p.end()


def dark_button(text: str, shade: str, parent: QWidget, action: str) -> QPushButton:
    b=QPushButton(text,parent)
    b.setMinimumHeight(51)
    b.setIcon(QIcon(str(ASSETS / f"icon_{action}.png")))
    b.setIconSize(QSize(22,22))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFont(font(13,True))
    b.setStyleSheet(f'''
        QPushButton {{ background:{shade}; color:#F8E8C4; border:2px solid #C99B59;
                      border-radius:9px; padding:7px 13px; }}
        QPushButton:hover {{ background:#986638; border:2px solid #F0D293; }}
        QPushButton:pressed {{ background:#34241C; }}
        QPushButton:disabled {{ background:#706356; color:#C4AD91; border-color:#93806A; }}
        QPushButton:focus {{ border:2px solid #FFF0A6; }}
    ''')
    return b


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.game=GameModel()
        writable = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not writable:
            writable = str(Path.home()/'.sanguo_huarongdao')
        self.records=RecordStore(Path(writable)/'best.json')
        self.best=self.records.load()
        self.settings = QSettings('OrangePerfume', 'SanGuoHuaRongDao')
        self.language = normalize_language(self.settings.value('ui/language', DEFAULT_LANGUAGE))
        self.animation_speed = str(self.settings.value('game/animation_speed', 'normal'))
        if self.animation_speed not in ANIMATION_DURATIONS_MS:
            self.animation_speed = 'normal'
        self.setWindowTitle(tr(self.language, 'window_title'))
        self.setWindowIcon(QIcon(str(ASSETS/'icon.png')))
        self.setMinimumSize(990,700)
        self.resize(1170,840)
        self._init_ui()
        self.timer=QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._update_stats)
        self.timer.start()
        self._update_stats()

    def _init_ui(self) -> None:
        root=TextureBackground()
        self.setCentralWidget(root)
        page=QVBoxLayout(root)
        page.setContentsMargins(23,12,23,14)
        page.setSpacing(7)
        titlebar=QHBoxLayout()
        titles=QVBoxLayout()
        titles.setSpacing(0)
        title=QLabel(tr(self.language, 'main_title'))
        self.title_label = title
        title.setFont(font(29,True))
        title.setStyleSheet('color:#F6D9A2;')
        subtitle=QLabel(tr(self.language, 'subtitle'))
        self.subtitle_label = subtitle
        subtitle.setFont(font(11))
        subtitle.setStyleSheet('color:#D3AE7D; padding-top:2px;')
        titles.addWidget(title)
        titles.addWidget(subtitle)
        titlebar.addLayout(titles, 1)
        edition=QLabel(tr(self.language, 'edition'))
        self.edition_label = edition
        edition.setWordWrap(True)
        edition.setFont(font(11,True))
        edition.setStyleSheet('color:#E7C999; background:#50301D; border:1px solid #9E7147; border-radius:11px; padding:10px 14px;')
        titlebar.addWidget(edition)
        self.language_button = QPushButton(root)
        self.language_button.setObjectName('languageButton')
        self.language_button.setMinimumHeight(38)
        self.language_button.setMinimumWidth(164)
        self.language_button.setFont(font(10, True))
        self.language_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language_button.setStyleSheet("""
            QPushButton { color:#F7DEAF; background:#50301D; border:1px solid #C69A62;
                          border-radius:8px; padding:7px 10px; }
            QPushButton:hover { background:#755030; border-color:#F0D293; }
            QPushButton::menu-indicator { image:none; }
        """)
        self.language_menu = QMenu(self.language_button)
        self.language_menu.setObjectName('languageMenu')
        self.language_menu.setStyleSheet("""
            QMenu { background:#F5E4C6; color:#54341E; border:1px solid #A77B4A; }
            QMenu::item { padding:8px 22px; }
            QMenu::item:selected { background:#D8B786; }
            QMenu::item:checked { font-weight:bold; }
        """)
        self.language_group = QActionGroup(self.language_menu)
        self.language_group.setExclusive(True)
        self.language_actions = {}
        for locale, visible_name in LANGUAGES:
            action = QAction(visible_name, self.language_menu)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, chosen=locale: self.set_language(chosen))
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[locale] = action
        self.language_button.setMenu(self.language_menu)
        titlebar.addWidget(self.language_button)
        page.addLayout(titlebar)
        main=QHBoxLayout()
        main.setSpacing(17)
        self.board=BoardWidget(self.game)
        self.board.set_animation_speed(self.animation_speed)
        self.board.move_requested.connect(self._make_move)
        self.board.group_move_requested.connect(self._make_group_move)
        self.board.selection_changed.connect(self._on_selection_changed)
        main.addWidget(self.board,5)
        side=ParchmentPanel()
        # 外层侧栏可滚动：极小窗口/高 DPI 下即便控制区本身变高，
        # 仍可到达底部提示框，而不是让布局把其裁切。
        self.side_scroll = QScrollArea()
        self.side_scroll.setObjectName('sideScroll')
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.side_scroll.setMinimumWidth(300)
        self.side_scroll.setMaximumWidth(400)
        self.side_scroll.setStyleSheet('''
            QScrollArea#sideScroll { background:transparent; border:none; }
            QScrollBar:vertical { background:#50321E; width:11px; }
            QScrollBar::handle:vertical { background:#B38A59; border-radius:4px; min-height:24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:none; }
        ''')
        side.setMinimumWidth(0)
        side.setMaximumWidth(400)
        side_layout=QVBoxLayout(side)
        side_layout.setContentsMargins(27,24,27,22)
        side_layout.setSpacing(12)
        header=QLabel(tr(self.language, 'chapter_title'))
        self.chapter_header = header
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(font(24,True))
        header.setStyleSheet('color:#532C1C; background:transparent;')
        side_layout.addWidget(header)
        tagline=QLabel(tr(self.language, 'chapter_subtitle'))
        self.tagline_label = tagline
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setFont(font(11,True))
        tagline.setStyleSheet('color:#885B3F; background:transparent;')
        side_layout.addWidget(tagline)
        line=QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet('color:#B89360; background:#B89360;')
        side_layout.addWidget(line)
        info=QLabel(tr(self.language, 'description'))
        self.intro_label = info
        info.setWordWrap(True)
        info.setFont(font(12))
        info.setStyleSheet('color:#5C3927; background:transparent; line-height:1.5;')
        side_layout.addWidget(info)
        progress=QLabel(tr(self.language, 'progress'))
        self.progress_title_label = progress
        progress.setFont(font(13,True))
        progress.setStyleSheet('color:#62402B; background:transparent; padding-top:7px;')
        side_layout.addWidget(progress)
        metrics=QHBoxLayout()
        metrics.setSpacing(12)
        self.steps_label=self._metric(tr(self.language, 'moves'),'0')
        self.time_label=self._metric(tr(self.language, 'time'),'00:00')
        metrics.addWidget(self.steps_label.parentWidget())
        metrics.addWidget(self.time_label.parentWidget())
        side_layout.addLayout(metrics)
        self.best_label=QLabel()
        self.best_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.best_label.setWordWrap(True)
        self.best_label.setFont(font(10,True))
        self.best_label.setStyleSheet('color:#775136; background:transparent;')
        side_layout.addWidget(self.best_label)
        controls=QLabel(tr(self.language, 'controls'))
        self.controls_label = controls
        controls.setFont(font(13,True))
        controls.setStyleSheet('color:#62402B; background:transparent; padding-top:9px;')
        side_layout.addWidget(controls)
        self.reset_button=dark_button(tr(self.language, 'restart'),'#396751',side,'restart')
        self.undo_button=dark_button(tr(self.language, 'undo'),'#365D7B',side,'undo')
        self.pause_button=dark_button(tr(self.language, 'pause'),'#654D6B',side,'pause')
        for button in (self.reset_button,self.undo_button,self.pause_button):
            side_layout.addWidget(button)
        self.reset_button.clicked.connect(self._restart)
        self.undo_button.clicked.connect(self._undo)
        self.pause_button.clicked.connect(self._pause)
        speed_title = QLabel(tr(self.language, 'speed_heading'))
        self.speed_title_label = speed_title
        speed_title.setFont(font(11, True))
        speed_title.setStyleSheet('color:#62402B; background:transparent; padding-top:7px;')
        side_layout.addWidget(speed_title)
        self.speed_combo = QComboBox(side)
        self.speed_combo.setObjectName('animationSpeed')
        self.speed_combo.setFont(font(11))
        for value in ('slow', 'normal', 'fast'):
            self.speed_combo.addItem(tr(self.language, 'speed_' + value), value)
        self.speed_combo.setCurrentIndex(self.speed_combo.findData(self.animation_speed))
        self.speed_combo.setMinimumHeight(38)
        self.speed_combo.setToolTip(tr(self.language, 'speed_tooltip'))
        self.speed_combo.setStyleSheet("""
            QComboBox {background:#F3DFC1; color:#54341E; border:1px solid #C59B6C;
                       border-radius:7px; padding:6px 10px;}
            QComboBox QAbstractItemView {background:#F3DFC1; color:#54341E;
                                        selection-background-color:#C59B6C;}
        """)
        self.speed_combo.currentIndexChanged.connect(self._change_animation_speed)
        side_layout.addWidget(self.speed_combo)
        self.selected_info=QLabel(tr(self.language, 'selection_prefix', names=tr(self.language, 'selection_none')))
        self.selected_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_info.setWordWrap(True)
        self.selected_info.setFont(font(11))
        self.selected_info.setStyleSheet('color:#714C37; background:transparent; padding-top:6px;')
        side_layout.addWidget(self.selected_info)
        # 玩法提示作为独立的可滚动区域：低分辨率、高 DPI 和窄侧栏下
        # 不会再依赖 QLabel 被压缩后的固定高度，亦不会裁切最后几行说明。
        self.help_scroll = QScrollArea(side)
        self.help_scroll.setObjectName('helpScroll')
        self.help_scroll.setWidgetResizable(True)
        self.help_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.help_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.help_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.help_scroll.setMinimumHeight(112)
        self.help_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.help_scroll.setStyleSheet('''
            QScrollArea#helpScroll { background:#F5E4C6;
                border:1px solid #C9A87F; border-radius:8px; }
            QScrollArea#helpScroll > QWidget > QWidget { background:#F5E4C6; }
            QScrollBar:vertical { background:#E9D4AF; width:11px; margin:3px; }
            QScrollBar::handle:vertical { background:#A77B4A; border-radius:4px; min-height:24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:none; }
        ''')
        help_content = QWidget()
        help_content.setObjectName('helpContent')
        help_content.setStyleSheet('background:#F5E4C6;')
        help_layout = QVBoxLayout(help_content)
        help_layout.setContentsMargins(13,11,13,12)
        help_layout.setSpacing(4)
        help_heading = QLabel(tr(self.language, 'help_title'))
        self.help_heading_label = help_heading
        help_heading.setFont(font(12,True))
        help_heading.setStyleSheet('color:#593A27; background:transparent;')
        help_layout.addWidget(help_heading)
        # 使用短句和分组说明；布局负责换行，长文字可向下滚动查看。
        self.help_labels = []
        self.help_titles = []
        self.help_sections = {}
        for section_id in HELP_IDS:
            heading_label = QLabel(tr(self.language, f'help.{section_id}.title'))
            heading_label.setFont(font(10, True))
            heading_label.setStyleSheet('color:#68452F; background:transparent;')
            help_layout.addWidget(heading_label)
            description_label = QLabel(tr(self.language, f'help.{section_id}.body'))
            description_label.setWordWrap(True)
            description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            description_label.setFont(font(10))
            description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            description_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            description_label.setStyleSheet('color:#63442D; background:transparent;')
            help_layout.addWidget(description_label)
            help_layout.addSpacing(5)
            self.help_labels.append(description_label)
            self.help_titles.append(heading_label)
        self._index_help_sections()
        self.help_scroll.setWidget(help_content)
        side_layout.addWidget(self.help_scroll, 1)
        self.side_scroll.setWidget(side)
        main.addWidget(self.side_scroll,3)
        page.addLayout(main,1)
        foot=QLabel(tr(self.language, 'footer'))
        self.footer_label = foot
        foot.setFont(font(10))
        foot.setWordWrap(True)
        foot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        foot.setStyleSheet('color:#D7B88C; padding:6px 4px;')
        page.addWidget(foot)
        QShortcut(QKeySequence('Ctrl+Z'),self,activated=self._undo)
        QShortcut(QKeySequence('R'),self,activated=self._restart)
        QShortcut(QKeySequence('Space'),self,activated=self._pause)
        self._apply_language()
        self.board.setFocus()

    def _index_help_sections(self) -> None:
        """Keep the indexed help descriptions consistent with the active locale."""
        self.help_sections = {
            tr(self.language, f'help.{section_id}.title'): self.help_labels[i]
            for i, section_id in enumerate(HELP_IDS)
        }

    def _on_selection_changed(self, names: str) -> None:
        self.selected_info.setText(tr(self.language, 'selection_prefix', names=names))

    def set_language(self, language: str, persist: bool = True) -> None:
        """Translate all UI surfaces in place without resetting the game or timers."""
        self.language = normalize_language(language)
        self._apply_language()
        if persist:
            self.settings.setValue('ui/language', self.language)
            self.settings.sync()
        self.board.setFocus()

    def _apply_language(self) -> None:
        language = self.language
        t = lambda key, **kwargs: tr(language, key, **kwargs)
        self.setWindowTitle(t('window_title'))
        self.title_label.setText(t('main_title'))
        self.title_label.setFont(font(23 if language == 'en' else 29, True))
        self.subtitle_label.setText(t('subtitle'))
        self.edition_label.setText(t('edition'))
        self.language_button.setText(t('language_button'))
        self.language_button.setToolTip(t('language_tooltip'))
        self.language_actions[language].setChecked(True)
        self.chapter_header.setText(t('chapter_title'))
        self.chapter_header.setFont(font(18 if language == 'en' else 24, True))
        self.tagline_label.setText(t('chapter_subtitle'))
        self.intro_label.setText(t('description'))
        self.progress_title_label.setText(t('progress'))
        self.steps_caption.setText(t('moves'))
        self.time_caption.setText(t('time'))
        self.controls_label.setText(t('controls'))
        self.reset_button.setText(t('restart'))
        self.undo_button.setText(t('undo'))
        self.speed_title_label.setText(t('speed_heading'))
        self.speed_combo.setToolTip(t('speed_tooltip'))
        with QSignalBlocker(self.speed_combo):
            for i in range(self.speed_combo.count()):
                self.speed_combo.setItemText(i, t('speed_' + self.speed_combo.itemData(i)))
        self.help_heading_label.setText(t('help_title'))
        for i, section_id in enumerate(HELP_IDS):
            self.help_titles[i].setText(t(f'help.{section_id}.title'))
            self.help_labels[i].setText(t(f'help.{section_id}.body'))
        self._index_help_sections()
        self.footer_label.setText(t('footer'))
        self.board.set_language(language)
        self._update_stats()

    def _change_animation_speed(self, _index: int) -> None:
        speed = self.speed_combo.currentData()
        if speed not in ANIMATION_DURATIONS_MS:
            return
        self.animation_speed = speed
        self.board.set_animation_speed(speed)
        self.settings.setValue('game/animation_speed', speed)
        self.settings.sync()
        self.board.setFocus()

    def _metric(self, caption: str, value: str) -> QLabel:
        card=QFrame(self)
        card.setStyleSheet('QFrame {background:#F3DFC1; border:1px solid #C59B6C; border-radius:10px;} QLabel{border:none; background:transparent;}')
        v=QVBoxLayout(card)
        v.setContentsMargins(7,8,7,9)
        v.setSpacing(3)
        name=QLabel(caption)
        name.setObjectName('metricCaption')
        if caption == tr(self.language, 'moves'):
            self.steps_caption = name
        else:
            self.time_caption = name
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setFont(font(10,True))
        name.setStyleSheet('color:#755239;')
        number=QLabel(value)
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFont(font(22,True))
        number.setStyleSheet('color:#4A2C1D;')
        v.addWidget(name)
        v.addWidget(number)
        return number

    def _update_stats(self) -> None:
        self.steps_label.setText(str(self.game.steps))
        elapsed=int(self.game.elapsed)
        self.time_label.setText(f'{elapsed//60:02}:{elapsed%60:02}')
        self.undo_button.setEnabled(bool(self.game.history) and not self.game.paused)
        self.pause_button.setText(tr(self.language, 'resume' if self.game.paused else 'pause'))
        self.pause_button.setIcon(QIcon(str(ASSETS / ('icon_play.png' if self.game.paused else 'icon_pause.png'))))
        self.pause_button.setEnabled(self.game.running or self.game.paused)
        self.best_label.setText(
            tr(self.language, 'best', steps=self.best['steps'],
               time=f"{self.best['seconds']//60:02}:{self.best['seconds']%60:02}")
            if self.best else tr(self.language, 'best_none')
        )
        self.board.update()

    def _make_move(self,index:int,dx:int,dy:int,count:int) -> None:
        old=self.game.positions[index]
        changed=self.game.move(index,dx,dy,count)
        if changed:
            self.board.hide_targets()
            self.board.animate(index,old)
            self._update_stats()
            if self.game.finished:
                QTimer.singleShot(self.board.animation_duration_ms + 50, self._win)

    def _make_group_move(self, indices: tuple[int, ...], dx: int, dy: int, count: int) -> None:
        original = {i: self.game.positions[i] for i in indices}
        changed = self.game.move_group(indices, dx, dy, count)
        if changed:
            self.board.hide_targets()
            self.board.animate_group(original)
            self._update_stats()
            if self.game.finished:
                QTimer.singleShot(self.board.animation_duration_ms + 50, self._win)

    def _win(self) -> None:
        if not self.game.finished:
            return
        seconds=int(self.game.elapsed)
        score_saved=True
        try:
            if self.records.update_best(self.game.steps,seconds):
                self.best=self.records.load()
        except OSError:
            score_saved=False
        self._update_stats()
        message = tr(self.language, 'win_message', steps=self.game.steps,
                     time=f'{seconds//60:02}:{seconds%60:02}')
        if not score_saved:
            message += '\n\n' + tr(self.language, 'win_save_error')
        dialog = QMessageBox(self)
        dialog.setWindowTitle(tr(self.language, 'win_title'))
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.button(QMessageBox.StandardButton.Ok).setText(tr(self.language, 'dialog_ok'))
        dialog.exec()

    def _undo(self) -> None:
        before = self.game.positions
        if self.game.undo():
            old_positions = {i: old for i, old in enumerate(before)
                             if old != self.game.positions[i]}
            self.board.clear_selection()
            self.board.animate_group(old_positions)
            self._update_stats()

    def _restart(self) -> None:
        if self.game.steps:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(tr(self.language, 'restart_title'))
            dialog.setIcon(QMessageBox.Icon.Question)
            dialog.setText(tr(self.language, 'restart_confirm'))
            dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            dialog.button(QMessageBox.StandardButton.Yes).setText(tr(self.language, 'confirm_yes'))
            dialog.button(QMessageBox.StandardButton.No).setText(tr(self.language, 'confirm_no'))
            if dialog.exec() != QMessageBox.StandardButton.Yes:
                return
        self.game.reset()
        self.board.clear_selection()
        self.board.clear_animation()
        self.selected_info.setText(tr(self.language, 'selection_prefix',
                                      names=tr(self.language, 'selection_none')))
        self._update_stats()
        self.board.setFocus()

    def _pause(self) -> None:
        self.game.toggle_pause()
        self._update_stats()
        self.board.setFocus()


def run() -> int:
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('SanGuoHuaRongDao')
    app.setOrganizationName('HuaRongDao')
    app.setFont(font(11))
    window=MainWindow()
    window.show()
    return app.exec()
