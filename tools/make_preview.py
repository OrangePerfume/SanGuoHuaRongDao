"""生成使用本项目素材的静态视觉预览（不是 Qt 游戏窗口截图）。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'huarongdao'/'assets'
FONT_PATH=subprocess.check_output(['fc-match','-f','%{file}','Noto Serif CJK SC'],text=True).strip()
FONT_SANS=subprocess.check_output(['fc-match','-f','%{file}','Noto Sans CJK SC'],text=True).strip()

def ft(size,bold=False):
    return ImageFont.truetype(FONT_PATH if bold else FONT_SANS,size)

def centered(draw,xy,text,fill,font):
    x,y=xy
    bbox=draw.textbbox((0,0),text,font=font)
    draw.text((x-(bbox[2]-bbox[0])/2,y-(bbox[3]-bbox[1])/2-bbox[1]),text,font=font,fill=fill)

def cover(im,size,bias_y=.45):
    w,h=size
    iw,ih=im.size
    scale=max(w/iw,h/ih)
    nw,nh=int(iw*scale)+1,int(ih*scale)+1
    im=im.resize((nw,nh),Image.Resampling.LANCZOS)
    x=(nw-w)//2
    y=int((nh-h)*bias_y)
    return im.crop((x,y,x+w,y+h))

base=Image.new('RGB',(1300,960),(33,19,13))
scene=Image.open(ASSETS/'red_cliffs.jpg').convert('RGB')
scene=scene.resize((1440,960),Image.Resampling.LANCZOS)
base.paste(scene,(-270,0))
# The independent illustration extends behind the parchment panel.
base=Image.blend(base,Image.new('RGB',base.size,(19,12,8)),.22)
d=ImageDraw.Draw(base)
d.text((32,19),'三 国 华 容 道',fill=(250,221,167),font=ft(38,True))
d.text((34,72),'经典棋局 · 一局不急，步步有谋',fill=(239,210,160),font=ft(17))
for x,w,label in ((748,98,'棋局'),(856,178,'语言：简体中文'),(1044,106,'设置'),(1160,106,'关于')):
    d.rounded_rectangle((x,35,x+w,80),radius=8,fill='#50301D',outline='#C69A62',width=2)
    centered(d,(x+w/2,57),label,'#F7DEAF',ft(17,True))
# Board frame
bx,by,s=86,168,130
bw,bh=4*s,5*s
outer=(bx-26,by-26,bx+bw+26,by+bh+26)
d.rounded_rectangle((outer[0]+7,outer[1]+8,outer[2]+7,outer[3]+8),radius=18,fill=(10,6,5))
d.rounded_rectangle(outer,radius=16,fill=(96,60,30),outline=(221,161,82),width=5)
d.rounded_rectangle((bx-11,by-11,bx+bw+11,by+bh+11),radius=7,fill=(56,33,20),outline=(128,78,43),width=6)
wood=Image.open(ASSETS/'wood_board.jpg').convert('RGB')
base.paste(cover(wood,(bw,bh)),(bx,by))
d=ImageDraw.Draw(base)
for i in range(1,4):d.line((bx+i*s,by,bx+i*s,by+bh),fill=(71,41,23),width=2)
for i in range(1,5):d.line((bx,by+i*s,bx+bw,by+i*s),fill=(71,41,23),width=2)
d.rounded_rectangle((bx+32,by-66,bx+bw-32,by-26),radius=10,fill='#432415',outline='#E2B76D',width=3)
centered(d,(bx+bw/2,by-46),'—  横  刀  立  马  —',(238,194,117),ft(24,True))
d.rounded_rectangle((bx+s,by+bh+18,bx+3*s,by+bh+57),radius=9,fill=(209,155,77),outline=(99,51,20),width=3)
centered(d,(bx+2*s,by+bh+36),'▼  华 容 道 出 口  ▼',(74,36,16),ft(19,True))
# Tiles. Coordinates match core.
import sys
sys.path.insert(0,str(ROOT))
from huarongdao.core import PIECES,START
names=['caocao','guanyu','zhangfei','zhaoyun','machao','huangzhong','soldier']
colors=['#AC3C37','#53704C','#93543C','#56788A','#537390','#A87947','#8C6247']
for i,(piece,pos) in enumerate(zip(PIECES,START)):
    nx,ny=pos%4,pos//4
    tile=(bx+nx*s+4,by+ny*s+4,bx+(nx+piece.w)*s-4,by+(ny+piece.h)*s-4)
    x0,y0,x1,y1=tile
    w,h=x1-x0,y1-y0
    d.rounded_rectangle((x0+2,y0+4,x1+2,y1+4),radius=9,fill=(20,12,9))
    d.rounded_rectangle(tile,radius=10,fill=(108,72,44),outline=(225,172,96),width=3)
    name=names[i] if i<len(names) else 'soldier'
    portrait=Image.open(ASSETS/'portraits'/f'{name}.png').convert('RGB')
    pic=cover(portrait,(w-10,h-10-31),.32 if piece.h==1 else .46)
    mask=Image.new('L',(w-10,h-10-31))
    md=ImageDraw.Draw(mask)
    md.rounded_rectangle((0,0,mask.width,mask.height+8),radius=7,fill=255)
    base.paste(pic,(x0+5,y0+5),mask)
    d=ImageDraw.Draw(base)
    d.rectangle((x0+5,y1-37,x1-5,y1-5),fill=(41,24,20))
    d.line((x0+5,y1-37,x1-5,y1-37),fill=(208,161,95),width=2)
    centered(d,((x0+x1)/2,y1-22),'兵' if i>=6 else piece.name,(253,231,185),ft(21 if w>200 else 19,True))
    d.rounded_rectangle(tile,radius=9,outline=(245,196,110),width=2)
# A legal example from the real opening: recommendation from the solver.
from huarongdao.hint import next_move
from huarongdao.i18n import piece_name, tr
from huarongdao.core import display_hint_rectangles
hint=next_move(START)
piece=PIECES[hint.piece]
for x,y,w,h in display_hint_rectangles(START,(hint.piece,)):
    area=(bx+x*s+7,by+y*s+7,bx+(x+w)*s-7,by+(y+h)*s-7)
    d.rounded_rectangle(area,radius=9,fill='#6D7950',outline='#D8F0B4',width=3)
x,y=START[hint.piece]%4,START[hint.piece]//4
area=(bx+x*s+5,by+y*s+5,bx+(x+piece.w)*s-5,by+(y+piece.h)*s-5)
d.rounded_rectangle(area,radius=10,outline='#FFD66B',width=5)
# Compact selection plaque, not a third column.
px=bx+bw+36; py=by+185
box=(px,py,px+75,py+286)
d.rounded_rectangle(box,radius=14,fill='#8F2515',outline='#F4C361',width=3)
d.rounded_rectangle((px+6,py+6,px+69,py+280),radius=10,outline='#D89F4B',width=1)
for j,ch in enumerate('当前选中'):
    centered(d,(px+37,py+37+j*30),ch,'#F5D9A0',ft(23,True))
for j,ch in enumerate(piece_name('zh-CN',hint.piece)):
    centered(d,(px+37,py+176+j*36),ch,'#FFDC72',ft(28,True))
# Right parchment panel, grouped controls and a dedicated hint card.
px,py,pw,ph=848,108,422,784
parchment=Image.open(ASSETS/'parchment.jpg').convert('RGB')
patch=cover(parchment,(pw,ph)); mask=Image.new('L',patch.size)
ImageDraw.Draw(mask).rounded_rectangle((0,0,*patch.size),radius=13,fill=255)
base.paste(patch,(px,py),mask);d=ImageDraw.Draw(base)
d.rounded_rectangle((px,py,px+pw,py+ph),radius=13,outline='#BD925B',width=3)
ink='#62402B'
def panel(y,h,title):
    d.rounded_rectangle((px+14,y,px+pw-14,y+h),radius=10,fill='#F4E3C4',outline='#D7B883',width=2)
    d.text((px+28,y+10),title,fill=ink,font=ft(22,True))
def button(x,y,w,h,label,color):
    d.rounded_rectangle((x,y,x+w,y+h),radius=8,fill=color,outline='#C99B59',width=2)
    centered(d,(x+w/2,y+h/2),label,'#F8E8C4',ft(19,True))
panel(py+14,168,'棋局进度')
for ix,lab in enumerate(['移动步数','游戏用时']):
    cx=px+28+ix*184
    d.rounded_rectangle((cx,py+62,cx+176,py+142),radius=9,fill='#F8E8CE',outline='#C59B6C',width=2)
    centered(d,(cx+88,py+84),lab,ink,ft(16))
    centered(d,(cx+88,py+116),'0' if ix==0 else '00:00','#4A2C1D',ft(30,True))
centered(d,(px+pw/2,py+162),'最佳纪录：尚未通关',ink,ft(16))
panel(py+194,154,'棋局操作')
button(px+28,py+237,176,42,'撤销上一步','#365D7B')
button(px+212,py+237,176,42,'暂停游戏','#654D6B')
button(px+28,py+287,360,42,'重新开始','#396751')
panel(py+360,201,'解题提示')
portrait=Image.open(ASSETS/'portraits'/f'{names[hint.piece] if hint.piece<len(names) else "soldier"}.png').convert('RGB')
base.paste(cover(portrait,(62,62)),(px+28,py+405));d=ImageDraw.Draw(base)
d.rounded_rectangle((px+28,py+405,px+90,py+467),radius=5,outline='#C79B52',width=2)
direction=tr('zh-CN','solution_'+{(-1,0):'left',(1,0):'right',(0,-1):'up',(0,1):'down'}[hint.dx,hint.dy])
d.text((px+104,py+405),f"推荐：{piece_name('zh-CN',hint.piece)} · {hint.source//4+1}行{hint.source%4+1}列",font=ft(17,True),fill=ink)
d.text((px+104,py+434),f'向{direction}移动一格',font=ft(20,True),fill='#A44121')
button(px+28,py+490,176,42,'下一步提示','#79532E')
button(px+212,py+490,176,42,'清除提示','#A5845B')
panel(py+573,74,'棋子滑动速度')
button(px+250,py+591,138,39,'标准  ▼','#79532E')
button(px+14,py+661,pw-28,49,'玩法提示  ▼','#79532E')
d.rounded_rectangle((22,910,1278,944),radius=6,fill='#352016')
d.text((36,916),'提示：绿色轮廓表示合法目标位置，Ctrl+点击可多选。金色边框标记推荐棋子。',fill='#F6D9A2',font=ft(16))
base.save(ROOT/'PREVIEW.png',optimize=True)
print(ROOT/'PREVIEW.png')
