"""三国华容道桌面界面：彩色木纹棋盘与人物画像。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal,
    QStandardPaths,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QKeySequence, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .core import BOARD_W, BOARD_H, PIECES, START, occupied_by, shifted
from .model import GameModel
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
        self._selected: int | None = None
        self._pressed_pos: QPointF | None = None
        self._pressed_index: int | None = None
        self._preview: tuple[int, int] | None = None
        self._anim_index: int | None = None
        self._anim_from = 0
        self._anim_t = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(145)
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

    def _at(self, point: QPointF) -> int | None:
        x0, y0, unit = self._layout()
        cx = math.floor((point.x() - x0) / unit)
        cy = math.floor((point.y() - y0) / unit)
        return occupied_by(self.game.positions, cx, cy)

    def _frame(self, value: object) -> None:
        self._anim_t = float(value)
        self.update()

    def _end_animation(self) -> None:
        self._anim_index = None
        self._anim_t = 1.0
        self.update()

    def animate(self, index: int, original_pos: int) -> None:
        self._animation.stop()
        self._anim_index = index
        self._anim_from = original_pos
        self._anim_t = 0.0
        self._animation.start()

    def clear_animation(self) -> None:
        self._animation.stop()
        self._anim_index = None
        self._anim_t = 1.0
        self._pressed_index = None
        self._pressed_pos = None
        self._preview = None
        self.update()

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
        # 所有棋子按逻辑位置绘制；移动中的棋子额外做平滑插值。
        for i in range(len(PIECES)):
            rect = self._piece_rect(i)
            if self._anim_index == i:
                old = list(self.game.positions)
                old[i] = self._anim_from
                old_rect = self._piece_rect(i,tuple(old))
                rect = QRectF(
                    old_rect.x() + (rect.x()-old_rect.x())*self._anim_t,
                    old_rect.y() + (rect.y()-old_rect.y())*self._anim_t,
                    rect.width(),rect.height(),
                )
            if self._preview is not None and i == self._pressed_index:
                # 拖动时显示半透明原位置，同时在合法目的地预览。
                pi, destination=self._preview
                new = list(self.game.positions)
                new[pi] = destination
                if destination != self.game.positions[pi]:
                    painter.setOpacity(0.34)
                    self._draw_piece(painter,i,rect,True)
                    painter.setOpacity(1)
                    rect=self._piece_rect(i,tuple(new))
            self._draw_piece(painter,i,rect,i == self._selected)
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
        if event.button()!=Qt.MouseButton.LeftButton or self.game.paused or self.game.finished:
            return
        self.setFocus()
        self._pressed_pos=event.position()
        self._pressed_index=self._at(event.position())
        self._selected=self._pressed_index
        self._preview=None
        if self._selected is not None:
            self.selection_changed.emit(PIECES[self._selected].name if self._selected<6 else "小兵")
        self.update()

    def mouseMoveEvent(self,event) -> None:
        if self._pressed_pos is None or self._pressed_index is None or self.game.paused:
            return
        direction=self._drag_direction(event.position()-self._pressed_pos)
        self._preview=None
        if direction is not None:
            dx,dy,count=direction
            candidate=self.game.positions
            for _ in range(count):
                next_state=shifted(candidate,self._pressed_index,dx,dy)
                if next_state is None:
                    break
                candidate=next_state
            if candidate != self.game.positions:
                dest=candidate[self._pressed_index]
                self._preview=(self._pressed_index,dest)
        self.update()

    def mouseReleaseEvent(self,event) -> None:
        if event.button()!=Qt.MouseButton.LeftButton:
            return
        if self._pressed_pos is not None and self._pressed_index is not None:
            direction=self._drag_direction(event.position()-self._pressed_pos)
            if direction is not None:
                dx,dy,count=direction
                self.move_requested.emit(self._pressed_index,dx,dy,count)
        self._pressed_pos=None
        self._pressed_index=None
        self._preview=None
        self.update()

    def keyPressEvent(self,event) -> None:
        if self.game.paused or self.game.finished:
            super().keyPressEvent(event)
            return
        key=event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            inc=-1 if key==Qt.Key.Key_Backtab else 1
            self._selected=((self._selected if self._selected is not None else -1)+inc)%len(PIECES)
            self.selection_changed.emit(PIECES[self._selected].name if self._selected<6 else "小兵")
            self.update()
            event.accept()
            return
        direction={
            Qt.Key.Key_Left: (-1,0),Qt.Key.Key_A: (-1,0),
            Qt.Key.Key_Right: (1,0),Qt.Key.Key_D: (1,0),
            Qt.Key.Key_Up: (0,-1),Qt.Key.Key_W: (0,-1),
            Qt.Key.Key_Down: (0,1),Qt.Key.Key_S: (0,1),
        }.get(key)
        if direction and self._selected is not None:
            self.move_requested.emit(self._selected,*direction,1)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        if not self.game.paused and not self.game.finished:
            increment = 1 if next else -1
            self._selected = ((self._selected if self._selected is not None else (-1 if next else 0)) + increment) % len(PIECES)
            self.selection_changed.emit(PIECES[self._selected].name if self._selected < 6 else "小兵")
            self.update()
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
        self.setWindowTitle('三国华容道 · 横刀立马  |  V0.1.0')
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
        self.board.move_requested.connect(self._make_move)
        self.board.selection_changed.connect(lambda name: self.selected_info.setText('当前选中：'+name))
        main.addWidget(self.board,5)
        side=ParchmentPanel()
        side.setMinimumWidth(300)
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
        self.selected_info=QLabel('当前选中：无')
        self.selected_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_info.setFont(font(11))
        self.selected_info.setStyleSheet('color:#714C37; background:transparent; padding-top:6px;')
        side_layout.addWidget(self.selected_info)
        side_layout.addStretch(1)
        rules=QLabel('玩法提示\n\n鼠标：按住人物棋子拖动\n键盘：点击选中棋子后按方向键 / WASD\n快捷键：Ctrl+Z 撤销 · R 重开 · 空格暂停\n\n每移动一格记一步，棋子不可旋转。')
        rules.setWordWrap(True)
        rules.setFont(font(10))
        rules.setStyleSheet('color:#63442D; border:1px solid #C9A87F; border-radius:8px; background:#F5E4C6; padding:10px 12px;')
        side_layout.addWidget(rules)
        main.addWidget(side,3)
        page.addLayout(main,1)
        foot=QLabel('提示：拖动可连续移动多格；棋子移动前会检查整条路径是否畅通。')
        foot.setFont(font(10))
        foot.setStyleSheet('color:#D7B88C; padding:6px 4px;')
        page.addWidget(foot)
        QShortcut(QKeySequence('Ctrl+Z'),self,activated=self._undo)
        QShortcut(QKeySequence('R'),self,activated=self._restart)
        QShortcut(QKeySequence('Space'),self,activated=self._pause)
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
            self.board.animate(index,old)
            self._update_stats()
            if self.game.finished:
                QTimer.singleShot(210,self._win)

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
        if self.game.undo():
            self.board.clear_animation()
            self._update_stats()

    def _restart(self) -> None:
        if self.game.steps:
            if QMessageBox.question(self,'重新开始','确定要放弃当前棋局并重新开始吗？',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.game.reset()
        self.board._selected=None
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
