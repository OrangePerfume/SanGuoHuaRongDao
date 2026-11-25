"""三国华容道桌面界面：彩色木纹棋盘与人物画像。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal,
    QSettings, QStandardPaths,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QKeySequence, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .core import BOARD_W, PIECES, destination_footprints, occupied_by, shifted_group, target_for_click
from .model import GameModel
from .motion import ANIMATION_DURATIONS_MS, MotionTrack
from .records import RecordStore

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
        """每个合法终点画完整棋子外框，按棋子形状计算，而非逐格高亮。"""
        if not self._selected or not self._targets_visible or self.game.paused or self.game.finished:
            return ()
        x0, y0, unit = self._layout()
        return tuple(
            QRectF(x0 + cx * unit + 7, y0 + cy * unit + 7,
                   width * unit - 14, height * unit - 14)
            for _destination, footprints in destination_footprints(
                self.game.positions, tuple(sorted(self._selected))
            )
            for _index, cx, cy, width, height in footprints
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

    def _emit_selection(self) -> None:
        self._targets_visible = bool(self._selected)
        names = [PIECES[i].name if i < 6 else '小兵' for i in sorted(self._selected)]
        if not names:
            self.selection_changed.emit('无')
        elif len(names) == 1:
            self.selection_changed.emit(names[0])
        else:
            self.selection_changed.emit(f'{len(names)} 枚 · ' + '、'.join(names))
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
        painter.setFont(font(label_size, True))
        name = "兵" if i >= 6 else PIECES[i].name
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
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "—  横 刀 立 马  —")
        # 底部出口：两格宽位置
        exit_rect = QRectF(x0+unit, y0+5*unit+12, 2*unit, 27)
        painter.setBrush(c("#D4A15C"))
        painter.setPen(QPen(c("#72411F"),2))
        painter.drawRoundedRect(exit_rect,5,5)
        painter.setPen(c("#512A17"))
        painter.setFont(font(12,True))
        painter.drawText(exit_rect, Qt.AlignmentFlag.AlignCenter, "▼  华 容 道 出 口  ▼")
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
        # 移动提示按「整块棋子在目标位置的占地矩形」绘制。
        # 绘制在棋子之上，含与原位置重合的区域，确保 1×2 / 2×1 / 2×2
        # 分别是一整个长方形 / 大正方形，而不是数个互不相连的 1×1 色块。
        for hint in self._hint_rects():
            painter.setBrush(c('#8CC786', 65))
            painter.setPen(QPen(c('#D8F0B4', 215), 2.2))
            painter.drawRoundedRect(hint, 9, 9)
        if self.game.paused:
            painter.fillRect(board_rect,c("#120B08",188))
            painter.setPen(c("#F2D6A0"))
            painter.setFont(font(28,True))
            painter.drawText(board_rect, Qt.AlignmentFlag.AlignCenter, "已暂停")
        if self.game.finished:
            painter.setBrush(c("#1A3929",228))
            plaque=QRectF(x0+unit*.35,y0+unit*2.15,unit*3.3,unit*.75)
            painter.setPen(QPen(c("#E8CA88"),2))
            painter.drawRoundedRect(plaque,12,12)
            painter.setPen(c("#FFE9B6"))
            painter.setFont(font(20,True))
            painter.drawText(plaque, Qt.AlignmentFlag.AlignCenter, "曹操脱困 · 恭喜通关")
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
        self.animation_speed = str(self.settings.value('game/animation_speed', 'normal'))
        if self.animation_speed not in ANIMATION_DURATIONS_MS:
            self.animation_speed = 'normal'
        self.setWindowTitle('三国华容道 · 横刀立马  |  V0.3.0')
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
        title=QLabel('三 国 华 容 道')
        title.setFont(font(29,True))
        title.setStyleSheet('color:#F6D9A2;')
        subtitle=QLabel('经典棋局 · 横刀立马     |     一局不急，步步有谋')
        subtitle.setFont(font(11))
        subtitle.setStyleSheet('color:#D3AE7D; padding-top:2px;')
        titles.addWidget(title)
        titles.addWidget(subtitle)
        titlebar.addLayout(titles)
        titlebar.addStretch()
        edition=QLabel('原创国风人物棋子  ·  离线单机')
        edition.setFont(font(11,True))
        edition.setStyleSheet('color:#E7C999; background:#50301D; border:1px solid #9E7147; border-radius:11px; padding:10px 14px;')
        titlebar.addWidget(edition)
        page.addLayout(titlebar)
        main=QHBoxLayout()
        main.setSpacing(17)
        self.board=BoardWidget(self.game)
        self.board.set_animation_speed(self.animation_speed)
        self.board.move_requested.connect(self._make_move)
        self.board.group_move_requested.connect(self._make_group_move)
        self.board.selection_changed.connect(lambda name: self.selected_info.setText('当前选中：'+name))
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
        header=QLabel('横 刀 立 马')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(font(24,True))
        header.setStyleSheet('color:#532C1C; background:transparent;')
        side_layout.addWidget(header)
        tagline=QLabel('壹 · 经典篇')
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setFont(font(11,True))
        tagline.setStyleSheet('color:#885B3F; background:transparent;')
        side_layout.addWidget(tagline)
        line=QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet('color:#B89360; background:#B89360;')
        side_layout.addWidget(line)
        info=QLabel('调动众将，助曹操从棋盘底部中央的出口脱困。')
        info.setWordWrap(True)
        info.setFont(font(12))
        info.setStyleSheet('color:#5C3927; background:transparent; line-height:1.5;')
        side_layout.addWidget(info)
        progress=QLabel('棋 局 进 度')
        progress.setFont(font(13,True))
        progress.setStyleSheet('color:#62402B; background:transparent; padding-top:7px;')
        side_layout.addWidget(progress)
        metrics=QHBoxLayout()
        metrics.setSpacing(12)
        self.steps_label=self._metric('移动步数','0')
        self.time_label=self._metric('游戏用时','00:00')
        metrics.addWidget(self.steps_label.parentWidget())
        metrics.addWidget(self.time_label.parentWidget())
        side_layout.addLayout(metrics)
        self.best_label=QLabel()
        self.best_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.best_label.setWordWrap(True)
        self.best_label.setFont(font(10,True))
        self.best_label.setStyleSheet('color:#775136; background:transparent;')
        side_layout.addWidget(self.best_label)
        controls=QLabel('操 作 区')
        controls.setFont(font(13,True))
        controls.setStyleSheet('color:#62402B; background:transparent; padding-top:9px;')
        side_layout.addWidget(controls)
        self.reset_button=dark_button('重新开始','#396751',side,'restart')
        self.undo_button=dark_button('撤销上一步','#365D7B',side,'undo')
        self.pause_button=dark_button('暂停游戏','#654D6B',side,'pause')
        for button in (self.reset_button,self.undo_button,self.pause_button):
            side_layout.addWidget(button)
        self.reset_button.clicked.connect(self._restart)
        self.undo_button.clicked.connect(self._undo)
        self.pause_button.clicked.connect(self._pause)
        speed_title = QLabel('棋子滑动速度')
        speed_title.setFont(font(11, True))
        speed_title.setStyleSheet('color:#62402B; background:transparent; padding-top:7px;')
        side_layout.addWidget(speed_title)
        self.speed_combo = QComboBox(side)
        self.speed_combo.setObjectName('animationSpeed')
        self.speed_combo.setFont(font(11))
        for text, value in (('慢', 'slow'), ('标准', 'normal'), ('快', 'fast')):
            self.speed_combo.addItem(text, value)
        self.speed_combo.setCurrentIndex(self.speed_combo.findData(self.animation_speed))
        self.speed_combo.setMinimumHeight(38)
        self.speed_combo.setToolTip('调整棋子移动与撤销的滑动速度，设置自动保存。')
        self.speed_combo.setStyleSheet("""
            QComboBox {background:#F3DFC1; color:#54341E; border:1px solid #C59B6C;
                       border-radius:7px; padding:6px 10px;}
            QComboBox QAbstractItemView {background:#F3DFC1; color:#54341E;
                                        selection-background-color:#C59B6C;}
        """)
        self.speed_combo.currentIndexChanged.connect(self._change_animation_speed)
        side_layout.addWidget(self.speed_combo)
        self.selected_info=QLabel('当前选中：无')
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
        help_heading = QLabel('玩 法 提 示')
        help_heading.setFont(font(12,True))
        help_heading.setStyleSheet('color:#593A27; background:transparent;')
        help_layout.addWidget(help_heading)
        # 使用短句和分组说明；布局负责换行，长文字可向下滚动查看。
        help_entries = (
            ('点击 / 拖动', '选中人物后点击绿色目标位置，或按住棋子拖动。'),
            ('多人同向移动', 'Ctrl+点击多枚棋子，再同向拖动或点击目标位置。'),
            ('绿色提示', '按整块棋子占位显示；移动成功后自动清除。'),
            ('键盘操作', '方向键 / WASD 移动选中棋子。'),
            ('快捷键', 'Ctrl+Z 撤销 · Esc 取消选中\nR 重开 · 空格暂停/继续'),
            ('计步与撤销', '每枚棋子每移动一格记一步；整组移动可一次撤销。'),
            ('滑动速度', '可选择慢、标准、快；移动和撤销均采用平滑动画。'),
        )
        self.help_labels = []
        self.help_sections = {}
        for heading, explanation in help_entries:
            heading_label = QLabel(heading)
            heading_label.setFont(font(10, True))
            heading_label.setStyleSheet('color:#68452F; background:transparent;')
            help_layout.addWidget(heading_label)
            description_label = QLabel(explanation)
            description_label.setWordWrap(True)
            description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            description_label.setFont(font(10))
            description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            description_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            description_label.setStyleSheet('color:#63442D; background:transparent;')
            help_layout.addWidget(description_label)
            help_layout.addSpacing(5)
            self.help_labels.append(description_label)
            self.help_sections[heading] = description_label
        self.help_scroll.setWidget(help_content)
        side_layout.addWidget(self.help_scroll, 1)
        self.side_scroll.setWidget(side)
        main.addWidget(self.side_scroll,3)
        page.addLayout(main,1)
        foot=QLabel('提示：绿色轮廓表示整块棋子的合法目标位置；点未被棋子占用的绿色区域即可移动。Ctrl+点击可多选。')
        foot.setFont(font(10))
        foot.setWordWrap(True)
        foot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        foot.setStyleSheet('color:#D7B88C; padding:6px 4px;')
        page.addWidget(foot)
        QShortcut(QKeySequence('Ctrl+Z'),self,activated=self._undo)
        QShortcut(QKeySequence('R'),self,activated=self._restart)
        QShortcut(QKeySequence('Space'),self,activated=self._pause)
        self.board.setFocus()

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
        self.pause_button.setText('继续游戏' if self.game.paused else '暂停游戏')
        self.pause_button.setIcon(QIcon(str(ASSETS / ('icon_play.png' if self.game.paused else 'icon_pause.png'))))
        self.pause_button.setEnabled(self.game.running or self.game.paused)
        self.best_label.setText(
            f'最佳纪录：{self.best["steps"]} 步 · {self.best["seconds"]//60:02}:{self.best["seconds"]%60:02}'
            if self.best else '最佳纪录：尚未通关'
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
        text=f'曹操已成功到达出口！\n\n本局走了 {self.game.steps} 步，用时 {seconds//60:02}:{seconds%60:02}。'
        if not score_saved:
            text+='\n\n注意：本地成绩保存失败，请检查用户数据目录权限。'
        QMessageBox.information(self,'恭喜通关',text)

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
            if QMessageBox.question(self,'重新开始','确定要放弃当前棋局并重新开始吗？',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.game.reset()
        self.board.clear_selection()
        self.board.clear_animation()
        self.selected_info.setText('当前选中：无')
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
