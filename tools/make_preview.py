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

base=Image.open(ASSETS/'wood_dark.jpg').convert('RGB').resize((1300,960),Image.Resampling.LANCZOS)
base=Image.blend(base,Image.new('RGB',(1300,960),(17,11,10)),.37)
d=ImageDraw.Draw(base)
d.text((50,22),'三 国 华 容 道',fill=(250,221,167),font=ft(42,True))
d.text((53,87),'经典棋局 · 横刀立马   |   一局不急，步步有谋',fill=(205,165,112),font=ft(18))
d.rounded_rectangle((1015,52,1250,91),radius=12,fill=(75,46,30),outline=(164,120,64),width=2)
centered(d,(1130,71),'原创彩色人物 · 离线单机',(255,222,173),ft(16))
# Board frame
bx,by,s=109,188,124
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
centered(d,(bx+bw/2,145),'—  横  刀  立  马  —',(238,194,117),ft(24,True))
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
# Panel
px,py,pw,ph=707,170,523,688
d.rounded_rectangle((px+8,py+10,px+pw+8,py+ph+10),radius=16,fill=(10,8,7))
d.rounded_rectangle((px,py,px+pw,py+ph),radius=16,fill=(231,206,163),outline=(170,115,57),width=6)
parchment=Image.open(ASSETS/'parchment.jpg').convert('RGB')
patch=cover(parchment,(pw-24,ph-24))
mask=Image.new('L',patch.size)
ImageDraw.Draw(mask).rounded_rectangle((0,0,*patch.size),radius=10,fill=255)
base.paste(patch,(px+12,py+12),mask)
d=ImageDraw.Draw(base)
centered(d,(px+pw/2,py+69),'横 刀 立 马',(82,42,26),ft(40,True))
centered(d,(px+pw/2,py+111),'壹 · 经典篇',(123,82,45),ft(19))
d.line((px+35,py+142,px+pw-35,py+142),fill=(172,126,70),width=2)
d.text((px+44,py+165),'调动众将，助曹操从棋盘底部中央',fill=(80,51,35),font=ft(19))
d.text((px+44,py+197),'的出口脱困。',fill=(80,51,35),font=ft(19))
d.text((px+44,py+253),'棋 局 进 度',fill=(94,57,38),font=ft(22,True))
for ix,lab in enumerate(['移动步数','游戏用时']):
    cx=px+47+ix*221
    d.rounded_rectangle((cx,py+307,cx+208,py+423),radius=11,fill=(246,225,188),outline=(183,144,98),width=2)
    centered(d,(cx+104,py+338),lab,(114,78,50),ft(19))
    centered(d,(cx+104,py+382),'0' if ix==0 else '00:00',(80,44,25),ft(39,True))
centered(d,(px+pw/2,py+453),'最佳纪录：尚未通关',(121,80,46),ft(18))
for i,(lab,bg) in enumerate([('重新开始',(47,104,79)),('撤销上一步',(47,86,122)),('暂停游戏',(97,72,104))]):
    y=py+488+i*68
    d.rounded_rectangle((px+41,y,px+pw-41,y+56),radius=10,fill=bg,outline=(195,152,84),width=3)
    act=['restart','undo','pause'][i]
    ic=Image.open(ASSETS/f'icon_{act}.png').convert('RGBA').resize((36,36),Image.Resampling.LANCZOS)
    base.paste(ic,(px+117,y+10),ic)
    centered(d,(px+pw/2+22,y+28),lab,(255,231,189),ft(23,True))
d.text((100,918),'操作：按住棋子拖动 · 点击选中后按方向键 / WASD · Ctrl+Z 撤销 · 空格暂停',fill=(209,175,128),font=ft(18))
base.save(ROOT/'PREVIEW.png',optimize=True)
print(ROOT/'PREVIEW.png')
