"""Usage: python3 samples.py [samples|playground] [--write]. Build drafts/<base>.jpg (+ samples_blind.jpg) and icon files from samples.json."""
import json, os, sys
from PIL import Image, ImageDraw
OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
DESTS = [os.path.join(ROOT, 'icons'), os.path.join(os.path.dirname(ROOT), 'Icon Display Station', 'icons')]
PAL = dict(W=(185,255,150), L=(131,180,106), G=(80,110,65), Y=(255,150,0), O=(255,60,0), R=(255,0,0),
  g=(20,160,0), D=(0,100,0), B=(0,0,255), S=(0,60,200), U=(100,0,255), N=(150,45,5), E=(80,20,0),
  P=(255,94,50), T=(180,60,10), C=(255,140,60), K=(0,0,0),
  A=(53,73,43), V=(180,200,0), H=(0,35,0), Q=(255,230,30), j=(100,230,0), o=(150,60,0), X=(30,8,0), Z=(0,15,0))  # A = bus tire dark grey (icons/bus.py); V lime, H deep green, Q pale belly, j light green, o ochre belly shadow
# LED->screen model (copied from build.py, port of display.js ledScreenRgb)
PRIM = [(0.7006,0.2993,400),(0.0743,0.8338,1150),(0.1241,0.0578,250)]
PRIM = [((x/y)*Iv, Iv, ((1-x-y)/y)*Iv) for x,y,Iv in PRIM]
LY = sum(p[1] for p in PRIM)
NEUTRAL = {(185,255,150): (242,242,242), (131,180,106): (170,170,170), (80,110,65): (110,110,110)}  # measured panel neutrals
def scr(d):
    if tuple(d) in NEUTRAL: return NEUTRAL[tuple(d)]
    X,Y,Z = [sum(d[j]/255*PRIM[j][i] for j in range(3))/LY for i in range(3)]
    out=[]
    for c in (3.2406*X-1.5372*Y-0.4986*Z, -0.9689*X+1.8758*Y+0.0415*Z, 0.0557*X-0.204*Y+1.057*Z):
        v=max(0,min(1,c)); out.append(round((12.92*v if v<=0.0031308 else 1.055*v**(1/2.4)-0.055)*255))
    return tuple(out)
def duty(rows):
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), rows
    return [[(0,0,0) if c == '.' else PAL[c] for c in r] for r in rows]
CELL = 14
def tile(rows):
    im = Image.new('RGB', (16*CELL, 16*CELL), (12,12,12)); dr = ImageDraw.Draw(im)
    for y, r in enumerate(duty(rows)):
        for x, d in enumerate(r):
            dr.ellipse([x*CELL+1, y*CELL+1, x*CELL+CELL-2, y*CELL+CELL-2], fill=scr(d) if any(d) else (24,24,24))
    return im
def sheet(icons, labels, path):
    n = len(icons); cols = 5; rws = (n+cols-1)//cols; W = 16*CELL+20; H = 16*CELL+(36 if labels else 20)
    im = Image.new('RGB', (cols*W, rws*H), (0,0,0)); dr = ImageDraw.Draw(im)
    for i, (name, rows) in enumerate(icons):
        x, y = (i % cols)*W+10, (i//cols)*H+10
        im.paste(tile(rows), (x, y))
        dr.text((x, y+16*CELL+4), name if labels else str(i+1), fill=(220,220,220))
    im.save(path, quality=92)
SRC = 'samples'
def write_icon(name, rows):
    lines = ['# Hand-edited 16x16 icon -- linear PWM duty bytes, row-major from top-left.',
             f'# From Stations/IconDisplay/drafts/{SRC}.json.', 'SIZE = (16, 16)', 'ICON = (']
    for r in duty(rows):
        lines.append('    ' + ', '.join(f'({a}, {b}, {c})' for a, b, c in r) + ',')
    lines.append(')')
    for d in DESTS:
        with open(os.path.join(d, name + '.py'), 'w') as f: f.write('\n'.join(lines) + '\n')
if __name__ == '__main__':
    base = next((a for a in sys.argv[1:] if not a.startswith('-')), 'samples')  # e.g. playground
    data = json.load(open(os.path.join(OUT, base + '.json')))
    icons = [(k, v['rows']) for k, v in data.items() if not k.startswith('_')]
    sheet(icons, True, os.path.join(OUT, base + '.jpg'))
    sheet(icons, False, os.path.join(OUT, base + '_blind.jpg'))
    SRC = base
    if '--write' in sys.argv:
        for k, rows in icons: write_icon(k, rows)
