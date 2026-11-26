"""三国华容道桌面界面：彩色木纹棋盘与人物画像。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal,
    QSettings, QSignalBlocker, QStandardPaths,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QIcon, QKeySequence, QLinearGradient,
    QAction, QActionGroup, QPainter, QPainterPath, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QMenu, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QDialog, QDialogButtonBox, QFormLayout, QSlider,
)

from . import __version__
from .core import (BOARD_W, BOARD_H, PIECES, display_hint_rectangles,
                   occupied_by, shifted_group, target_for_click)
from .model import GameModel
from .hint import NextMove, next_move, format_hint
from .motion import ANIMATION_DURATIONS_MS, MotionTrack
from .records import RecordStore
from .theme import board_layout, plaque_geometry, normalize_dimming
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


def wrap_to_available_width(label: QLabel) -> None:
    """Let translated labels wrap to the layout width, not widen a scroll panel.

    Preserve QLabel's height-for-width flag so layouts reserve enough vertical
    space for wrapped lines. Non-text controls keep their natural minimum size.
    """
    label.setWordWrap(True)
    policy = label.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
    policy.setHeightForWidth(True)
    label.setSizePolicy(policy)
    label.setMinimumWidth(0)


class SingleLineTitle(QLabel):
    """Fit complete header text to its actual width, without wrapping or eliding."""
    def __init__(self, text: str, point: int, bold: bool = False):
        super().__init__(text)
        self._preferred_font = font(point, bold)
        self._fitting = False
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setFont(self._preferred_font)
        self.setToolTip(text)

    def set_title(self, text: str, point: int, bold: bool = False) -> None:
        self._preferred_font = font(point, bold)
        self.setText(text)
        self.setToolTip(text)
        self._fit_text()

    def _fit_text(self) -> None:
        if not hasattr(self, '_preferred_font') or self._fitting:
            return
        available = self.contentsRect().width() - 2 * self.margin()
        if available <= 0:
            return
        self._fitting = True
        try:
            text = self.text()
            # Allow for glyph overhang and rounding at non-integral DPI.
            budget = max(1, available - 2)
            candidate = QFont(self._preferred_font)
            for point in range(self._preferred_font.pointSize(), 0, -1):
                candidate.setPointSize(point)
                metrics = (QFontMetrics(candidate), QFontMetrics(candidate, self))
                if all(max(m.horizontalAdvance(text), m.boundingRect(text).width()) <= budget
                       for m in metrics):
                    break
            if self.font() != candidate:
                self.setFont(candidate)
        finally:
            self._fitting = False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_text()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange,
                            QEvent.Type.DevicePixelRatioChange):
            self._fit_text()


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
    animation_settled = Signal()

    def __init__(self, game: GameModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.game = game
        self.language = DEFAULT_LANGUAGE
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(500, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._images = [QPixmap(str(ASSETS / "portraits" / f"{name}.png")) for name in PORTRAITS]
        self._board = QPixmap(str(ASSETS / "wood_board.jpg"))
        self.selection_plaque = None
        self._selected: set[int] = set()
        self.solution_hint: NextMove | None = None
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
        return board_layout(self.width(), self.height(), self.language)

    def position_selection_plaque(self) -> None:
        plaque = self.selection_plaque
        if plaque is None:
            return
        plaque.setGeometry(*plaque_geometry(self.width(), self.height(), self.language))
        plaque.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_selection_plaque()

    _PIECE_INSET = 3.0

    def _rect_at(self, index: int, x: float, y: float,
                 layout: tuple[float, float, float] | None = None) -> QRectF:
        x0, y0, unit = self._layout() if layout is None else layout
        piece = PIECES[index]
        inset = self._PIECE_INSET
        return QRectF(x0 + x * unit + inset, y0 + y * unit + inset,
                      piece.w * unit - 2 * inset, piece.h * unit - 2 * inset)

    def _piece_rect(self, index: int, positions: tuple[int, ...] | None = None,
                    layout: tuple[float, float, float] | None = None) -> QRectF:
        pos = (self.game.positions if positions is None else positions)[index]
        return self._rect_at(index, pos % BOARD_W, pos // BOARD_W, layout)

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

    def _displayed_piece_rect(self, index: int,
                              layout: tuple[float, float, float] | None = None) -> QRectF:
        """The current animated rectangle, shared by painting and hit testing."""
        x, y = self._motion.displayed(index, self.game.positions)
        return self._rect_at(index, x, y, layout)

    def _at(self, point: QPointF) -> int | None:
        layout = self._layout()
        rects = [(i, self._displayed_piece_rect(i, layout))
                 for i in reversed(range(len(PIECES)))]
        # Actual piece bodies take precedence over any other piece's margin.
        # In an overlap, the later-painted body is the visible top piece.
        for index, rect in rects:
            if rect.contains(point):
                return index
        # Restore the original full-cell hit area for a stationary piece;
        # moving pieces carry the same small margin with their visual position.
        inset = self._PIECE_INSET
        for index, rect in rects:
            area = rect.adjusted(-inset, -inset, inset, inset)
            if (area.left() <= point.x() < area.right()
                    and area.top() <= point.y() < area.bottom()):
                return index
        return None

    def _empty_target_cell(self, point: QPointF) -> tuple[int, int] | None:
        """A click destination must be both visually and logically empty."""
        x0, y0, unit = self._layout()
        cx = math.floor((point.x() - x0) / unit)
        cy = math.floor((point.y() - y0) / unit)
        if not (0 <= cx < BOARD_W and 0 <= cy < BOARD_H):
            return None
        if (occupied_by(self.game.positions, cx, cy) is not None
                or self._at(point) is not None):
            return None
        return cx, cy

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
        elif moving:
            self.animation_settled.emit()
        self.update()

    def _frame(self, value: object) -> None:
        self._motion.set_progress(float(value))
        self.update()

    def _end_animation(self) -> None:
        self._motion.complete()
        self.update()
        self.animation_settled.emit()

    def animate(self, index: int, original_pos: int) -> None:
        self.animate_group({index: original_pos})

    def animate_group(self, original_positions: dict[int, int]) -> None:
        active = self._motion.retarget(original_positions, self.game.positions)
        self._animation.stop()
        if active:
            self._animation.start()
        self.update()
        if not active:
            self.animation_settled.emit()

    def clear_animation(self) -> None:
        self._animation.stop()
        self._motion.complete()
        self._pressed_index = None
        self._pressed_pos = None
        self._preview = None
        self.update()
        self.animation_settled.emit()

    def clear_selection(self) -> None:
        self._selected.clear()
        self._emit_selection()

    def hide_targets(self) -> None:
        """成功移动后关闭落点提示；键盘操作仍可保留当前棋子选择。"""
        self._targets_visible = False
        self.update()

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)
        self.position_selection_plaque()
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
        # Gold rim, no pulsing or flashing; selection stays separate from hints.
        if selected:
            painter.setPen(QPen(c('#F8BD36'), 3))
            painter.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), 8, 8)
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
        # Keep the battlefield visible around the independently painted board.
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
        plaque_rect = title_rect.adjusted(-10, -5, 10, 8)
        painter.setBrush(c('#432415'))
        painter.setPen(QPen(c('#E2B76D'), 2.5))
        painter.drawRoundedRect(plaque_rect, 10, 10)
        painter.setPen(c("#F1D7A3"))
        painter.setFont(font(13 if self.language == 'en' else 15, True))
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
        layout = (x0, y0, unit)
        for i in range(len(PIECES)):
            rect = self._displayed_piece_rect(i, layout)
            if self._preview is not None and i in self._preview:
                ghost = list(self.game.positions)
                ghost[i] = self._preview[i]
                painter.setOpacity(0.30)
                self._draw_piece(painter, i, rect, True)
                painter.setOpacity(1.0)
                rect = self._piece_rect(i, tuple(ghost), layout)
            self._draw_piece(painter, i, rect, i in self._selected)
        # 同方向重叠落点先合并，再统一填充和描边，避免中间颜色加深。
        for hint in self._hint_rects():
            painter.setBrush(c('#8CC786', 65))
            painter.setPen(QPen(c('#D8F0B4', 215), 2.2))
            painter.drawRoundedRect(hint, 9, 9)
        if self.solution_hint is not None and not self.game.paused and not self.game.finished:
            # An advisory outline, separate from the normal green destinations.
            rect = self._displayed_piece_rect(self.solution_hint.piece, layout)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(c('#2F1C12'), 6))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 9, 9)
            painter.setPen(QPen(c('#FFD66B'), 3, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 9, 9)
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
        # A visually vacant but logically occupied destination is not an
        # empty-cell gesture, even if the board changes before mouse release.
        if index is None and self._empty_target_cell(event.position()) is None:
            self._pressed_pos = None
            self._pressed_index = None
            self._preview = None
            self.update()
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
            # Recheck the target: an animation may have moved a visible piece
            # under the pointer since the press. The core still owns legality.
            cell = self._empty_target_cell(event.position())
            if cell is not None:
                move = target_for_click(self.game.positions, tuple(sorted(self._selected)), *cell)
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
        if (key in (Qt.Key.Key_Q, Qt.Key.Key_E)
                and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            # Q/E select pieces; Tab and Shift+Tab retain normal focus navigation.
            increment = -1 if key == Qt.Key.Key_Q else 1
            previous = (next(iter(self._selected)) if len(self._selected) == 1
                        else (-1 if increment == 1 else 0))
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

    def wheelEvent(self,event) -> None:
        # 华容道不使用滚轮移动，以免与系统滚动误操作。
        event.ignore()


class SelectionPlaque(QLabel):
    """Compact red-and-gold text plaque; English is never letter-stacked."""
    def __init__(self, parent):
        super().__init__(parent)
        self.language = DEFAULT_LANGUAGE
        self.names = ''
        self.setWordWrap(True)
        self.setFont(font(10, True))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_selection(self, language, names):
        self.language, self.names = language, names
        self.setText(tr(language, 'selection_prefix', names=names))
        self.setToolTip(self.text())
        self.setAccessibleName(self.text())
        self.update()

    def display_text(self) -> str:
        heading = tr(self.language, 'selection_heading')
        if self.language != 'en' and len(self.names) <= 3:
            return '\n'.join(heading) + '\n\n' + '\n'.join(self.names)
        # Full names remain accessible and available as a tooltip. Limit only
        # the painted multi-selection text to keep the board area spacious.
        names = self.names.split(' · ', 1)[0] if len(self.names) > 22 else self.names
        return heading + '\n\n' + names

    def text_layout(self):
        horizontal_inset = 8 if self.language == 'en' else 10
        target = self.rect().adjusted(horizontal_inset, 12, -horizontal_inset, -12)
        flags = Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value
        text = self.display_text()
        start = 15 if self.language != 'en' and len(self.names) <= 3 else 11
        # Qt's word-wrap does not break an overwide word. Check the final
        # candidate too, including at 8pt and below, rather than returning an
        # unmeasured minimum. Measure against both the default screen and the
        # actual widget device, which can have a different DPI.
        for point in range(start, 0, -1):
            candidate = font(point, True)
            bounds = (QFontMetrics(candidate).boundingRect(target, flags, text),
                      QFontMetrics(candidate, self).boundingRect(target, flags, text))
            if all(r.width() <= target.width() and r.height() <= target.height()
                   for r in bounds):
                return target, flags, text, candidate
        # Only possible with an abnormally tiny widget, outside the supported
        # board geometry. Keep a valid font during transient resize events.
        return target, flags, text, font(1, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.names != tr(self.language, 'selection_none')
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, c('#AD351B' if active else '#594536'))
        grad.setColorAt(1, c('#68190D' if active else '#34271F'))
        painter.setBrush(grad)
        painter.setPen(QPen(c('#F4C361' if active else '#A58B67'), 2))
        painter.drawRoundedRect(rect, 12, 12)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(c('#D89F4B'), 1))
        painter.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 8, 8)
        painter.setPen(c('#F5D9A0'))
        target, flags, text, text_font = self.text_layout()
        painter.setFont(text_font)
        painter.drawText(target, flags, text)
        painter.end()


class TextureBackground(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._scene = QPixmap(str(ASSETS/'red_cliffs.jpg'))
        self._wood = QPixmap(str(ASSETS/'wood_dark.jpg'))
        self.dim = 22
        self.board = None
        self.panel = None

    def paintEvent(self,event) -> None:
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._scene.isNull():
            image_fill(p, self._wood, QRectF(self.rect()))
        else:
            # Anchor the two flags in the gap beside the board. Keep the CG's
            # original aspect ratio and fade to dark behind the controls.
            p.fillRect(self.rect(), c('#21130D'))
            w, h = self.width(), self.height()
            scene_w = max(w * .82, h * self._scene.width() / self._scene.height())
            scene_h = scene_w * self._scene.height() / self._scene.width()
            anchor = w * .58
            if self.board is not None and self.panel is not None:
                bx, _, cell = self.board._layout()
                edge = self.board.x() + bx + 4 * cell + 24
                anchor = (edge + self.panel.x()) / 2
            left = min(0.0, anchor - .70 * scene_w)
            right = left + scene_w
            p.drawPixmap(QRectF(left, (h - scene_h) / 2, scene_w, scene_h), self._scene,
                         QRectF(self._scene.rect()))
            if right < w:
                fade = QLinearGradient(QPointF(right - 90, 0), QPointF(right, 0))
                fade.setColorAt(0, c('#21130D', 0))
                fade.setColorAt(1, c('#21130D'))
                p.fillRect(QRectF(right - 90, 0, 90, h), fade)
        p.fillRect(self.rect(),c('#130C08',round(self.dim * 255 / 100)))
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


def dark_button(text: str, shade: str, parent: QWidget, action: str | None = None) -> QPushButton:
    b=QPushButton(text,parent)
    b.setMinimumHeight(51)
    if action is not None:
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
        self._hint_snapshot: tuple[int, ...] | None = None
        self._next_hint: NextMove | None = None
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
        self.background_dim = normalize_dimming(self.settings.value('ui/background_dim', 22))
        self.setWindowTitle(tr(self.language, 'window_title'))
        self.setWindowIcon(QIcon(str(ASSETS/'icon.png')))
        self.setMinimumSize(990,700)
        self.resize(1170,840)
        self._init_ui()
        self._win_pending = False
        self._restart_confirming = False
        self._win_timer = QTimer(self)
        self._win_timer.setSingleShot(True)
        self._win_timer.setInterval(50)
        self._win_timer.timeout.connect(self._win)
        self.board.animation_settled.connect(self._queue_win_dialog)
        self.board.animation_settled.connect(self._refresh_hint)
        self.timer=QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._update_stats)
        self.timer.start()
        self._update_stats()

    def _init_ui(self) -> None:
        root=TextureBackground()
        self.background = root
        root.dim = self.background_dim
        self.setCentralWidget(root)
        page=QVBoxLayout(root)
        page.setContentsMargins(23,12,23,14)
        page.setSpacing(7)
        titlebar=QHBoxLayout()
        titles=QVBoxLayout()
        titles.setSpacing(0)
        title=SingleLineTitle(tr(self.language, 'main_title'), 20 if self.language == 'en' else 28, True)
        self.title_label = title
        title.setStyleSheet('color:#F6D9A2; background:rgba(33,17,12,130); border-radius:6px;')
        subtitle=SingleLineTitle(tr(self.language, 'subtitle'), 11)
        self.subtitle_label = subtitle
        subtitle.setStyleSheet('color:#F2D3A1; background:rgba(33,17,12,130); padding-top:2px;')
        titles.addWidget(title)
        titles.addWidget(subtitle)
        titlebar.addLayout(titles, 1)
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
        self.settings_button = dark_button(tr(self.language, 'settings'), '#50301D', root)
        self.about_button = dark_button(tr(self.language, 'about'), '#50301D', root)
        for button in (self.settings_button, self.about_button):
            button.setMinimumHeight(38)
            button.setFont(font(10, True))
            titlebar.addWidget(button)
        self.settings_button.clicked.connect(self._open_settings)
        self.about_button.clicked.connect(self._open_about)
        page.addLayout(titlebar)
        main=QHBoxLayout()
        main.setSpacing(17)
        self.board=BoardWidget(self.game)
        self.board.set_animation_speed(self.animation_speed)
        self.board.move_requested.connect(self._make_move)
        self.board.group_move_requested.connect(self._make_group_move)
        self.board.selection_changed.connect(self._on_selection_changed)
        self.selected_info = SelectionPlaque(self.board)
        self.board.selection_plaque = self.selected_info
        self.selected_info.set_selection(self.language, tr(self.language, 'selection_none'))
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
        self.side_scroll.setMinimumWidth(400 if self.language == "en" else 300)
        self.side_scroll.setMaximumWidth(430)
        self.side_scroll.setStyleSheet('''
            QScrollArea#sideScroll { background:transparent; border:none; }
            QScrollBar:vertical { background:#50321E; width:11px; }
            QScrollBar::handle:vertical { background:#B38A59; border-radius:4px; min-height:24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:none; }
        ''')
        side.setMinimumWidth(0)
        side_layout=QVBoxLayout(side)
        self.side_layout = side_layout
        side_layout.setContentsMargins(27,24,27,22)
        side_layout.setSpacing(8)
        header=QLabel(tr(self.language, 'chapter_title'))
        self.chapter_header = header
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(font(24,True))
        wrap_to_available_width(header)
        header.setStyleSheet('color:#532C1C; background:transparent;')

        tagline=QLabel(tr(self.language, 'chapter_subtitle'))
        self.tagline_label = tagline
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setFont(font(11,True))
        wrap_to_available_width(tagline)
        tagline.setStyleSheet('color:#885B3F; background:transparent;')

        line=QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet('color:#B89360; background:#B89360;')

        info=QLabel(tr(self.language, 'description'))
        self.intro_label = info
        info.setWordWrap(True)
        wrap_to_available_width(info)
        info.setFont(font(12))
        info.setStyleSheet('color:#5C3927; background:transparent; line-height:1.5;')

        progress=QLabel(tr(self.language, 'progress'))
        self.progress_title_label = progress
        progress.setFont(font(13,True))
        wrap_to_available_width(progress)
        progress.setStyleSheet('color:#62402B; background:transparent;')
        progress_card, progress_layout = self._section_card(side)
        progress_layout.addWidget(progress)
        metrics=QHBoxLayout()
        metrics.setSpacing(12)
        self.steps_label=self._metric(tr(self.language, 'moves'),'0')
        self.time_label=self._metric(tr(self.language, 'time'),'00:00')
        metrics.addWidget(self.steps_label.parentWidget())
        metrics.addWidget(self.time_label.parentWidget())
        progress_layout.addLayout(metrics)
        self.best_label=QLabel()
        self.best_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.best_label.setWordWrap(True)
        wrap_to_available_width(self.best_label)
        self.best_label.setFont(font(10,True))
        self.best_label.setStyleSheet('color:#775136; background:transparent;')
        progress_layout.addWidget(self.best_label)
        side_layout.addWidget(progress_card)
        controls=QLabel(tr(self.language, 'controls'))
        self.controls_label = controls
        controls.setFont(font(13,True))
        wrap_to_available_width(controls)
        controls.setStyleSheet('color:#62402B; background:transparent;')
        action_card, action_layout = self._section_card(side)
        action_layout.addWidget(controls)
        self.reset_button=dark_button(tr(self.language, 'restart'),'#396751',side,'restart')
        self.undo_button=dark_button(tr(self.language, 'undo'),'#365D7B',side,'undo')
        self.pause_button=dark_button(tr(self.language, 'pause'),'#654D6B',side,'pause')
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        for button in (self.undo_button,self.pause_button):
            button.setMinimumHeight(44)
            button.setFont(font(10, True))
            button.setIconSize(QSize(18, 18))
            button.setStyleSheet(button.styleSheet().replace('padding:7px 13px;', 'padding:5px 6px;'))
            action_row.addWidget(button, 1)
        self.reset_button.setMinimumHeight(44)
        action_layout.addLayout(action_row)
        action_layout.addWidget(self.reset_button)
        side_layout.addWidget(action_card)
        self.reset_button.clicked.connect(self._restart)
        self.undo_button.clicked.connect(self._undo)
        self.pause_button.clicked.connect(self._pause)
        self.hint_card = QFrame(side)
        self.hint_card.setObjectName('hintCard')
        self.hint_card.setStyleSheet('QFrame#hintCard {background:#F8E9CB; border:1px solid #C79B52; border-radius:10px;}')
        card_layout = QVBoxLayout(self.hint_card)
        card_layout.setContentsMargins(9, 8, 9, 9)
        card_layout.setSpacing(6)
        self.hint_heading = QLabel()
        self.hint_heading.setFont(font(12, True))
        wrap_to_available_width(self.hint_heading)
        self.hint_heading.setStyleSheet('color:#63402B; background:transparent;')
        card_layout.addWidget(self.hint_heading)
        hint_row = QHBoxLayout()
        self.hint_portrait = QLabel()
        self.hint_portrait.setFixedSize(58, 58)
        self.hint_portrait.setStyleSheet('border:1px solid #C79B52; border-radius:5px; background:#D9B47E;')
        self.hint_message = QLabel()
        wrap_to_available_width(self.hint_message)
        self.hint_message.setFont(font(10, True))
        self.hint_message.setStyleSheet('color:#895017; background:transparent;')
        self.hint_message.setTextFormat(Qt.TextFormat.PlainText)
        hint_row.addWidget(self.hint_portrait)
        hint_row.addWidget(self.hint_message, 1)
        card_layout.addLayout(hint_row)
        self.hint_button = dark_button(tr(self.language, 'solution_button'), '#79532E', self.hint_card)
        self.hint_button.setObjectName('nextMoveHint')
        self.clear_hint_button = dark_button(tr(self.language, 'solution_clear'), '#A5845B', self.hint_card)
        for button in (self.hint_button, self.clear_hint_button):
            button.setMinimumHeight(39)
            button.setFont(font(10, True))
            button.setStyleSheet(button.styleSheet().replace('padding:7px 13px;', 'padding:5px 6px;'))
        self.hint_button.clicked.connect(self._request_hint)
        self.clear_hint_button.clicked.connect(self._dismiss_hint)
        hint_actions = QHBoxLayout()
        hint_actions.setSpacing(6)
        hint_actions.addWidget(self.hint_button, 1)
        hint_actions.addWidget(self.clear_hint_button, 1)
        card_layout.addLayout(hint_actions)
        side_layout.addWidget(self.hint_card)
        speed_title = QLabel(tr(self.language, 'speed_heading'))
        self.speed_title_label = speed_title
        speed_title.setFont(font(11, True))
        wrap_to_available_width(speed_title)
        speed_title.setStyleSheet('color:#62402B; background:transparent;')
        speed_row = QHBoxLayout()
        speed_row.addWidget(speed_title, 1)
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
        self.speed_combo.setMinimumWidth(100)
        speed_row.addWidget(self.speed_combo, 1)
        side_layout.addLayout(speed_row)
        self.help_toggle = QPushButton(side)
        self.help_toggle.setCheckable(True)
        self.help_toggle.setMinimumHeight(36)
        self.help_toggle.setFont(font(11, True))
        self.help_toggle.setStyleSheet('QPushButton { background:#F3DFC1; color:#54341E; border:1px solid #C59B6C; border-radius:8px; padding:6px; }')
        side_layout.addWidget(self.help_toggle)
        # 玩法提示作为独立的可滚动区域：低分辨率、高 DPI 和窄侧栏下
        # 不会再依赖 QLabel 被压缩后的固定高度，亦不会裁切最后几行说明。
        self.help_scroll = QScrollArea(side)
        self.help_scroll.setObjectName('helpScroll')
        self.help_scroll.setWidgetResizable(True)
        self.help_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.help_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.help_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.help_scroll.setMinimumHeight(112)
        # The nested scroll area must not propagate its contents' preferred
        # width to the surrounding side panel. Its text wraps inside the viewport.
        self.help_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
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
        self.help_layout = help_layout
        help_layout.setContentsMargins(13,11,13,12)
        help_layout.setSpacing(4)
        help_heading = QLabel(tr(self.language, 'help_title'))
        self.help_heading_label = help_heading
        help_heading.setFont(font(12,True))
        wrap_to_available_width(help_heading)
        help_heading.setStyleSheet('color:#593A27; background:transparent;')
        help_layout.addWidget(help_heading)
        # Keep context available without duplicating the large board title in the panel.
        for context in (header, tagline, line, info):
            help_layout.addWidget(context)
        # 使用短句和分组说明；布局负责换行，长文字可向下滚动查看。
        self.help_labels = []
        self.help_titles = []
        self.help_sections = {}
        for section_id in HELP_IDS:
            heading_label = QLabel(tr(self.language, f'help.{section_id}.title'))
            heading_label.setFont(font(10, True))
            wrap_to_available_width(heading_label)
            heading_label.setStyleSheet('color:#68452F; background:transparent;')
            help_layout.addWidget(heading_label)
            description_label = QLabel(tr(self.language, f'help.{section_id}.body'))
            description_label.setWordWrap(True)
            description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            description_label.setFont(font(10))
            description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            description_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            wrap_to_available_width(description_label)
            description_label.setStyleSheet('color:#63442D; background:transparent;')
            help_layout.addWidget(description_label)
            help_layout.addSpacing(5)
            self.help_labels.append(description_label)
            self.help_titles.append(heading_label)
        self._index_help_sections()
        self.help_scroll.setWidget(help_content)
        side_layout.addWidget(self.help_scroll, 1)
        self.help_toggle.toggled.connect(self.set_help_expanded)
        self.help_scroll.hide()
        side_layout.addStretch(1)
        self.help_spacer_index = side_layout.count() - 1
        self.side_scroll.setWidget(side)
        main.addWidget(self.side_scroll,3)
        root.board, root.panel = self.board, self.side_scroll
        page.addLayout(main,1)
        foot=QLabel(tr(self.language, 'footer'))
        self.footer_label = foot
        foot.setFont(font(10))
        foot.setWordWrap(True)
        foot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        foot.setStyleSheet('color:#F6D9A2; background:rgba(38,21,13,180); border-radius:6px; padding:5px 8px;')
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
        self.selected_info.set_selection(self.language, names)

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
        self.title_label.set_title(t('main_title'), 20 if language == 'en' else 28, True)
        self.subtitle_label.set_title(t('subtitle'), 11)
        self.settings_button.setText(t('settings'))
        self.about_button.setText(t('about'))
        self.language_button.setText(t('language_button'))
        self.language_button.setToolTip(t('language_tooltip'))
        self.language_actions[language].setChecked(True)
        self.chapter_header.setText(t('chapter_title'))
        self.chapter_header.setFont(font(18 if language == 'en' else 24, True))
        # Longer English text gets extra room, without shrinking the board below
        # its 500px minimum (990 - 46 margins - 17 spacing - 400 = 527px).
        # Revert to the original flexible widths when switching back to Chinese.
        self.side_scroll.setMinimumWidth(400 if language == 'en' else 300)
        margin = 15 if language == 'en' else 18
        self.side_layout.setContentsMargins(margin, 15, margin, 15)
        help_margin = 10 if language == 'en' else 13
        self.help_layout.setContentsMargins(help_margin, 11, help_margin, 12)
        self.tagline_label.setText(t('chapter_subtitle'))
        self.intro_label.setText(t('description'))
        self.progress_title_label.setText(t('progress'))
        self.steps_caption.setText(t('moves'))
        self.time_caption.setText(t('time'))
        self.controls_label.setText(t('controls'))
        self.reset_button.setText(t('restart'))
        self.undo_button.setText(t('undo'))
        self.hint_button.setToolTip(t('solution_tooltip'))
        self.hint_heading.setText(t('solution_heading'))
        self.clear_hint_button.setText(t('solution_clear'))
        self.set_help_expanded(self.help_toggle.isChecked())
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
        # Recompute both height-for-width layouts after replacing their text.
        self.help_layout.invalidate()
        self.side_layout.invalidate()
        self.help_scroll.widget().updateGeometry()
        self.side_scroll.widget().updateGeometry()
        self.help_scroll.updateGeometry()
        self.side_scroll.updateGeometry()
        self.background.update()

    def _change_animation_speed(self, _index: int) -> None:
        speed = self.speed_combo.currentData()
        if speed not in ANIMATION_DURATIONS_MS:
            return
        self.animation_speed = speed
        self.board.set_animation_speed(speed)
        self.settings.setValue('game/animation_speed', speed)
        self.settings.sync()
        self.board.setFocus()

    def _section_card(self, parent: QWidget) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(parent)
        card.setObjectName('sectionCard')
        card.setStyleSheet('QFrame#sectionCard {background:rgba(255,241,211,165); border:1px solid #D7B883; border-radius:10px;}')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(6)
        return card, layout

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
        wrap_to_available_width(name)
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
        self._refresh_hint()
        self.board.update()

    def _clear_hint(self) -> None:
        self._hint_snapshot = None
        self._next_hint = None
        self.board.solution_hint = None

    def _refresh_hint(self) -> None:
        if (self._hint_snapshot is not None and
                (self._hint_snapshot != self.game.positions or self.game.paused or self.game.finished)):
            self._clear_hint()
        active = self._hint_snapshot is not None
        self.hint_button.setEnabled(not self.game.paused and not self.game.finished
                                    and not self.board._motion.starts)
        self.hint_button.setText(tr(self.language, 'solution_button'))
        self.clear_hint_button.setEnabled(active)
        text = format_hint(self.language, self._next_hint) if active else tr(self.language, 'solution_idle')
        if self.hint_message.text() != text:
            self.hint_message.setText(text)
        hint = self._next_hint if active else None
        self.hint_portrait.setVisible(hint is not None)
        if hint is not None and self.hint_portrait.property('pieceIndex') != hint.piece:
            pixmap = self.board._images[hint.piece].scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                         Qt.TransformationMode.SmoothTransformation)
            self.hint_portrait.setPixmap(pixmap.copy((pixmap.width()-56)//2, (pixmap.height()-56)//2, 56, 56))
            self.hint_portrait.setProperty('pieceIndex', hint.piece)
        self.board.solution_hint = hint
        self.board.update()

    def _request_hint(self) -> None:
        if self.game.paused or self.game.finished or self.board._motion.starts:
            return
        self._next_hint = next_move(self.game.positions)
        self._hint_snapshot = self.game.positions
        self._refresh_hint()
        self.board.setFocus()

    def _dismiss_hint(self) -> None:
        self._clear_hint()
        self._refresh_hint()
        self.board.setFocus()

    def set_help_expanded(self, expanded: bool) -> None:
        with QSignalBlocker(self.help_toggle):
            self.help_toggle.setChecked(expanded)
        self.help_toggle.setText(tr(self.language, 'help_title') + ('  ▴' if expanded else '  ▾'))
        self.help_scroll.setVisible(expanded)
        self.side_layout.setStretch(self.help_spacer_index, 0 if expanded else 1)
        self.side_layout.invalidate()

    def _open_settings(self) -> None:
        t = lambda key: tr(self.language, key)
        dialog = QDialog(self)
        dialog.setWindowTitle(t('settings'))
        layout = QFormLayout(dialog)
        language = QComboBox(dialog)
        for key, name in LANGUAGES:
            language.addItem(name, key)
        language.setCurrentIndex(language.findData(self.language))
        speed = QComboBox(dialog)
        for key in ('slow', 'normal', 'fast'):
            speed.addItem(t('speed_' + key), key)
        speed.setCurrentIndex(speed.findData(self.animation_speed))
        dim = QSlider(Qt.Orientation.Horizontal, dialog)
        dim.setRange(0, 65)
        dim.setValue(self.background_dim)
        layout.addRow(t('language_heading'), language)
        layout.addRow(t('speed_heading'), speed)
        layout.addRow(t('background_dim'), dim)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t('dialog_ok'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t('confirm_no'))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if self._exec_preferences_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.background_dim = dim.value()
            self.background.dim = self.background_dim
            self.background.update()
            self.settings.setValue('ui/background_dim', self.background_dim)
            self.speed_combo.setCurrentIndex(self.speed_combo.findData(speed.currentData()))
            self.set_language(language.currentData())
            self.settings.sync()

    def _open_about(self) -> None:
        t = lambda key: tr(self.language, key)
        dialog = QDialog(self)
        dialog.setWindowTitle(t('about'))
        layout = QVBoxLayout(dialog)
        title = QLabel(t('main_title') + ' · V' + __version__)
        title.setFont(font(16, True))
        layout.addWidget(title)
        layout.addWidget(QLabel(t('edition')))
        layout.addWidget(QLabel('MIT License · OrangePerfume'))
        link = QLabel('<a href="https://github.com/OrangePerfume/SanGuoHuaRongDao">GitHub · SanGuoHuaRongDao</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        button = QPushButton(t('dialog_ok'))
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)
        self._exec_preferences_dialog(dialog)

    def _exec_preferences_dialog(self, dialog: QDialog) -> int:
        self._restart_confirming = True
        self._win_timer.stop()
        try:
            return dialog.exec()
        finally:
            self._restart_confirming = False
            self._queue_win_dialog()

    def _make_move(self,index:int,dx:int,dy:int,count:int) -> None:
        old=self.game.positions[index]
        changed=self.game.move(index,dx,dy,count)
        if changed:
            self.board.hide_targets()
            self.board.animate(index,old)
            self._update_stats()
            if self.game.finished:
                self._schedule_win()

    def _make_group_move(self, indices: tuple[int, ...], dx: int, dy: int, count: int) -> None:
        original = {i: self.game.positions[i] for i in indices}
        changed = self.game.move_group(indices, dx, dy, count)
        if changed:
            self.board.hide_targets()
            self.board.animate_group(original)
            self._update_stats()
            if self.game.finished:
                self._schedule_win()

    def _schedule_win(self) -> None:
        """Schedule a single notification for the current completed game."""
        self._win_pending = True
        self._queue_win_dialog()

    def _queue_win_dialog(self) -> None:
        # Start the short post-animation delay only after motion has settled.
        # A speed change can retarget motion, so do not use a fixed duration.
        if (self._win_pending and self.game.finished
                and not self._restart_confirming and not self.board._motion.starts
                and not self._win_timer.isActive()):
            self._win_timer.start()

    def _cancel_pending_win(self) -> None:
        self._win_pending = False
        self._win_timer.stop()

    def _win(self) -> None:
        if (not self._win_pending or not self.game.finished
                or self._restart_confirming or self.board._motion.starts):
            return
        # Consume the notification before opening a modal nested event loop.
        self._cancel_pending_win()
        self._show_win_dialog()

    def _show_win_dialog(self) -> None:
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
            self._cancel_pending_win()
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
            # Do not open a second modal dialog while restart is being confirmed.
            self._restart_confirming = True
            self._win_timer.stop()
            try:
                accepted = dialog.exec() == QMessageBox.StandardButton.Yes
            finally:
                self._restart_confirming = False
            if not accepted:
                self._queue_win_dialog()
                return
        self._cancel_pending_win()
        self.game.reset()
        self._clear_hint()
        self.board.clear_selection()
        self.board.clear_animation()
        self._on_selection_changed(tr(self.language, 'selection_none'))
        self._update_stats()
        self.board.setFocus()

    def closeEvent(self, event) -> None:
        self._cancel_pending_win()
        super().closeEvent(event)

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
