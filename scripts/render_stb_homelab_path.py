#!/usr/bin/env python3
"""Render the SixZuper STB-to-Mini-PC home-lab educational card."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
OUT = Path(__file__).resolve().parents[1] / 'media' / 'stb-to-minipc-homelab-20261021.png'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

im = Image.new('RGB', (W, H))
p = im.load()
for y in range(H):
    for x in range(W):
        edge = max(0, (x-460)/W)
        warm = max(0, 1-abs(y-490)/880)
        p[x,y] = (int(12+51*warm+19*edge), int(16+13*warm), int(31+3*warm))
d = ImageDraw.Draw(im)
orange = '#FF9854'; coral = '#FF5F4C'; white='#FFF8F3'; muted='#E1C5B9'
d.line((70,70,1010,70),fill='#B7563F',width=2)
d.rounded_rectangle((70,102,368,155),radius=22,fill='#411F23',outline=orange,width=2)
d.text((94,117),'SIXZUPER  /  LABS',font=f(21,True),fill=orange)
d.text((70,205),'HOME LAB',font=f(83,True),fill=white)
d.text((70,308),'MULAI DARI STB',font=f(59,True),fill=orange)
d.text((72,402),'Tidak perlu langsung beli server besar.',font=f(30),fill=muted)

items = [
 ('01', 'STB + LINUX', 'Belajar SSH, layanan ringan,', 'backup, dan akses jarak jauh.'),
 ('02', 'MINI PC', 'Naik kelas saat perlu RAM, SSD,', 'dan layanan berjalan bersamaan.'),
 ('03', 'PROXMOX VE', 'Di Mini PC x86_64: pisahkan', 'VM dan container untuk eksperimen.'),
]
for i,(num,title,line1,line2) in enumerate(items):
    top=516+i*218
    d.rounded_rectangle((70,top,1010,top+187),radius=26,fill='#271D29',outline='#934A3D',width=2)
    d.rounded_rectangle((95,top+25,173,top+97),radius=16,fill='#743532',outline=coral,width=2)
    d.text((111,top+43),num,font=f(31,True),fill=white)
    d.text((206,top+26),title,font=f(39,True),fill=orange)
    d.text((206,top+83),line1,font=f(26),fill=white)
    d.text((206,top+120),line2,font=f(26),fill=white)
    if i<2:
        cx=540
        d.line((cx,top+187,cx,top+212),fill=coral,width=5)
        d.polygon([(cx-10,top+202),(cx+10,top+202),(cx,top+217)],fill=coral)

d.rounded_rectangle((70,1200,1010,1280),radius=20,fill='#4B272B',outline=orange,width=2)
d.text((96,1224),'Mulai kecil. Pahami sistem. Baru tambah kapasitas.',font=f(25,True),fill=white)
d.text((70,1310),'SixZuper Labs  •  powered by Kilua',font=f(18),fill=muted)
OUT.parent.mkdir(exist_ok=True)
im.save(OUT,optimize=True)
print(OUT)
