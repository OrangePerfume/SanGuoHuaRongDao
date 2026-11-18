"""开发辅助：根据原创人物拼图生成角色 PNG，并制作程序图标及棋盘纹理。

人物母图是项目生成时原创插画，已预切片作为仓库 assets 的一部分。
此脚本仅再生成不依赖母图的木纹、纸张和图标。运行需要 Pillow。
"""
from __future__ import annotations

from pathlib import Path
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).resolve().parents[1] / 'huarongdao' / 'assets'
BASE.mkdir(parents=True, exist_ok=True)


def wood(name: str, width: int, height: int, palette: tuple[int,int,int], seed: int) -> None:
    r = random.Random(seed)
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((height, width))
    waves = (np.sin(yy / 7 + 0.9*np.sin(xx/87)) * 4.4
             + np.sin(yy / 23 + xx/174) * 5.5
             + np.sin(yy / 2.7 + np.sin(xx/31)) * 1.3)
    # 增加轻微噪声和细木纹；避免大面积棋盘呈纯色。
    grains = rng.normal(0, 3.7, (height, width))
    values = waves + grains
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for ch, base in enumerate(palette):
        arr[:,:,ch] = np.clip(base + values * (1 if ch == 0 else 0.83), 0, 255)
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im, 'RGBA')
    for _ in range(30):
        y = r.randrange(height)
        points = [(x, y + math.sin(x/45 + y)*1.7) for x in range(0, width+10, 10)]
        d.line(points, fill=(46, 23, 7, r.randint(8, 35)), width=r.choice((1, 1, 2)))
    im.save(BASE/name, optimize=True)


def parchment() -> None:
    rng = np.random.default_rng(99)
    w, h = 700, 1000
    yy, xx = np.indices((h,w))
    grain = rng.normal(0, 4.0, (h,w))
    mottle = 4*np.sin(xx/53)*np.sin(yy/47)
    vignette = np.clip(((xx-w/2)/(w/2))**2 + ((yy-h/2)/(h/2))**2,0,2)*9
    arr = np.zeros((h,w,3),dtype=np.uint8)
    for k,v in enumerate([235, 213, 175]):
        arr[:,:,k] = np.clip(v + grain + mottle - vignette,0,255)
    Image.fromarray(arr).save(BASE/'parchment.jpg',quality=91,optimize=True)


def action_icons() -> None:
    """绘制不依赖字体的按钮图标，避免 Windows 中文字体缺少符号。"""
    from PIL import ImageDraw
    for name in ('restart', 'undo', 'pause', 'play'):
        size=72
        canvas=Image.new('RGBA',(size,size),(0,0,0,0))
        dr=ImageDraw.Draw(canvas)
        gold=(248,220,166,255)
        if name=='restart':
            dr.arc((14,14,58,58),start=52,end=337,fill=gold,width=8)
            dr.polygon([(56,7),(62,29),(42,22)],fill=gold)
        elif name=='undo':
            dr.arc((25,19,64,58),start=80,end=280,fill=gold,width=8)
            dr.line([(12,30),(47,30)],fill=gold,width=8)
            dr.polygon([(9,30),(29,15),(29,45)],fill=gold)
        elif name=='pause':
            dr.rounded_rectangle((17,15,28,57),radius=3,fill=gold)
            dr.rounded_rectangle((44,15,55,57),radius=3,fill=gold)
        else:
            dr.polygon([(24,13),(24,59),(61,36)],fill=gold)
        canvas.save(BASE / (f'icon_{name}.png'), optimize=True)


def icon() -> None:
    size = 256
    im = Image.new('RGBA',(size,size),(0,0,0,0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6,6,250,250],radius=49,fill=(62,37,23),outline=(218,172,88),width=9)
    d.rounded_rectangle([20,20,236,236],radius=39,outline=(158,93,43),width=5)
    import subprocess
    fontpath = subprocess.check_output(['fc-match','-f','%{file}','Noto Serif CJK SC'],text=True).strip()
    font = ImageFont.truetype(fontpath,174)
    bbox = d.textbbox((0,0),'华',font=font)
    cx = (256-(bbox[2]-bbox[0]))/2-bbox[0]
    cy = (256-(bbox[3]-bbox[1]))/2-bbox[1]-8
    d.text((cx,cy),'华',font=font,fill=(247,215,147))
    im.save(BASE/'icon.png')
    im.save(BASE/'icon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__ == '__main__':
    wood('wood_board.jpg',900,1200,(136,85,45),31)
    wood('wood_dark.jpg',900,1200,(57,35,23),41)
    parchment()
    icon()
    action_icons()
    print('Generated board textures, parchment and icons')
