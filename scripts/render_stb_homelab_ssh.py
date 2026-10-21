#!/usr/bin/env python3
"""Render the second IG smoke-test card: first home-lab habits on an STB."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W,H=1080,1350
OUT=Path(__file__).resolve().parents[1]/'media/stb-homelab-ssh-backup-20261021.png'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(n,b=False):return ImageFont.truetype(BOLD if b else FONT,n)
im=Image.new('RGB',(W,H));px=im.load()
for y in range(H):
    for x in range(W):
        glow=max(0,1-((x-780)**2/(1050**2)+(y-360)**2/(950**2)))
        px[x,y]=(int(12+55*glow),int(17+14*glow),int(29+8*glow))
d=ImageDraw.Draw(im);orange='#FF9B55';coral='#FF6950';white='#FFF7EF';muted='#DEC5BA'
d.line((70,72,1010,72),fill='#B65E48',width=2)
d.rounded_rectangle((70,103,385,158),radius=23,fill='#41202A',outline=orange,width=2)
d.text((92,117),'SIXZUPER  /  LABS',font=f(22,True),fill=orange)
d.text((70,206),'STB JADI',font=f(79,True),fill=white)
d.text((70,310),'HOME LAB',font=f(79,True),fill=orange)
d.text((72,414),'Mulai dari 3 kebiasaan, bukan 3 mesin.',font=f(29),fill=muted)
steps=[
 ('01','AKSES VIA SSH','Kelola STB dari laptop di jaringanmu.','Amankan login sebelum buka akses luar.'),
 ('02','SATU LAYANAN','Jalankan layanan ringan lebih dulu.','Catat port, proses, dan kebutuhan RAM.'),
 ('03','BACKUP + UJI','Simpan konfigurasi dan data penting.','Coba pulihkan agar backup terbukti.')]
for i,(num,title,a,b) in enumerate(steps):
    y=515+i*219
    d.rounded_rectangle((70,y,1010,y+190),radius=28,fill='#2A202A',outline='#9A5143',width=2)
    d.rounded_rectangle((96,y+30,176,y+104),radius=18,fill='#713630',outline=coral,width=2)
    d.text((113,y+47),num,font=f(31,True),fill=white)
    d.text((210,y+30),title,font=f(36,True),fill=orange)
    d.text((210,y+91),a,font=f(24),fill=white)
    d.text((210,y+130),b,font=f(24),fill=white)
    if i<2:
        d.line((540,y+190,540,y+217),fill=coral,width=4)
        d.polygon(((528,y+207),(552,y+207),(540,y+223)),fill=coral)
d.rounded_rectangle((70,1200,1010,1280),radius=20,fill='#51292E',outline=orange,width=2)
d.text((97,1223),'Siap naik ke Mini PC? Pahami dasarnya dulu.',font=f(25,True),fill=white)
d.text((72,1310),'SixZuper Labs  •  powered by Kilua',font=f(18),fill=muted)
OUT.parent.mkdir(exist_ok=True)
im.save(OUT,optimize=True)
print(OUT)
