import math, json, os
import build as B
OUT = B.OUT
H = {}
def pad(rows):
    assert len(rows) <= 16 and all(len(r) <= 16 for r in rows), rows
    return [r.ljust(16, '.') for r in rows] + ['.'*16]*(16-len(rows))
def grid(): return [['.']*16 for _ in range(16)]
def done(g): return [''.join(r) for r in g]
def mirror(rows): return [r + r[::-1] for r in rows]
# taco: half-moon shell, filling on top
g = grid()
for y in range(4, 14):
    for x in range(16):
        if (x-7.5)**2 + ((y-4)*1.55)**2 <= 8.2**2: g[y][x] = 'Y'
for x,y in [(3,6),(9,7),(6,9),(12,6),(8,10),(4,8)]:
    if g[y][x]=='Y': g[y][x] = 'T'
fill = ["..g.g..g.g..g...", ".gRgNgRgNgRgNg..", "gNRNgNRNgNRgNRg."]
fill = [r[:15].rjust(16,'.')[0:16] for r in fill]
for y,r in enumerate(["...g..g...g..g..", "..gRgNgRgNgRgNg.", ".gNRNgNRNgNRgNRg"]):
    for x,c in enumerate(r):
        if c != '.': g[1+y][x] = c
H['taco'] = done(g)
# elote: cob, husk, stick
g = grid()
for y in range(0, 11):
    w = 3 if y > 0 else 2
    for x in range(8-w, 8+w):
        g[y][x] = 'Y' if (x+y) % 2 else 'C'
for y,r in enumerate(["..g..........g..", "..gg........gg..", "...gg......gg...", "....ggg..ggg....", ".....gggggg....."]):
    for x,c in enumerate(r):
        if c != '.': g[7+y][x] = c
for y in range(12, 16): g[y][7] = g[y][8] = 'N'
H['elote'] = done(g)
# concha: pink topping with 3 bold scored lines showing tan bread
g = grid()
for y in range(2, 12):
    for x in range(16):
        if (x-7.5)**2 + ((y-11)*0.95)**2 <= 7.8**2:
            a = math.degrees(math.atan2(11-y, x-7.5))
            g[y][x] = 'T' if (min(abs(a-k) for k in (45, 90, 135)) < 8 and y < 10 and y > 2) else 'P'
for y in (11, 12):
    for x in range(1, 15): g[y][x] = 'T'
g[13] = list("..TTTTTTTTTTTT..")
H['concha'] = done(g)
# churro: diagonal stick, ridges as alternating bands, sugar
g = grid()
for i in range(13):
    cx, cy = 2+i, 14-i
    for d in (-1, 0, 1):
        for e in (0, 1):
            x, y = cx+d+e, cy+d
            if 0 <= x < 16 and 0 <= y < 16: g[y][x] = 'C' if (x+y) % 3 == 0 else 'T'
for x,y in [(7,5),(12,3),(5,10)]: g[y][x] = 'W'
H['churro'] = done(g)
# tortillas: stack with top ellipse
g = grid()
for y in range(3, 10):
    for x in range(16):
        if ((x-7.5)/7.6)**2 + ((y-6)/3.2)**2 <= 1: g[y][x] = 'C'
for x,y in [(4,5),(9,4),(11,7),(6,7),(8,6)]: g[y][x] = 'T'
for k,y in enumerate(range(9, 14)):
    for x in range(1 if y < 13 else 2, 15 if y < 13 else 14): g[y][x] = 'T' if k % 2 == 0 else 'C'
H['tortillas'] = done(g)
# paleta: ice pop with fruit bits and stick
H['paleta'] = pad(['', '.....PPPPPP.....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '....PRPPPPRP....', '.......TT.......', '.......TT.......', '.......TT.......', '.......TT.......'])
# mango on a stick: flower-cut petals, chili
H['mango'] = pad(["...Y..Y..Y..Y...", "..YOY.YOY.YOY...", "..YYYYOYYYOYY...", "..YOYYYYOYYYY...", "...YYOYYYYOY....",
  "...YYYYOYYYY....", "...OYYYYYOYY....", "....YYOYYYY.....", "....YYYYOYY.....", ".....YYYYY......", "......YYY.......",
  ".......TT.......", ".......TT.......", ".......TT.......", ".......TT.......", ".......TT......."])
g = [list(r) for r in H['mango']]
for x,y in [(4,1),(7,1),(10,1),(5,4),(9,6)]: g[y][x] = 'R'
H['mango'] = done(g)
# pupusa: thick pale round (golden rim), bold griddle spots, big curtido pile
g = grid()
for y in range(1, 12):
    for x in range(13):
        if (x-6)**2 + ((y-6)*1.15)**2 <= 6.2**2: g[y][x] = 'C'
for y in (10, 11):
    for x in range(13):
        if g[y][x] == 'C' or (y == 11 and 2 <= x <= 10): g[y][x] = 'T'
for x,y in [(3,3),(4,3),(8,4),(9,4),(5,7),(6,7),(2,6),(10,7),(7,2)]: g[y][x] = 'N'
for y,r in enumerate(["..........g.O.g.", ".........gOgOgOg", "........OgggOggO", "........gOgOgggg"]):
    for x,c in enumerate(r):
        if c != '.': g[12+y][x] = c
H['pupusa'] = done(g)
# tamal: two unwrapped tamales seen from above, flat masa on open husks
leaf = ["", "...C...", "..CCC..", ".CCCCC.", ".CYYYC.", "CCYYYCC", "CCYRYCC", "CCYYYCC", "CCYRYCC", "CCYYYCC",
        "CCYRYCC", ".CYYYC.", ".CCCCC.", "..CCC..", "...C...", ""]
H['tamal'] = [('.' + l.ljust(7, '.') + l.ljust(7, '.') + '.') if l else '.'*16 for l in leaf]
# agua fresca: jamaica cup with straw and ice
H['agua_fresca'] = pad(["...........W....", "..........W.....", ".........W......", "..WWWWWWWWWWWW..", "..RRRRRRWRRRRR..",
  "..RLLRRRWRRRRR..", "...RLLRRWRLLR...", "...RRRRRWRLLR...", "...RRRRRRRRRR...", "....RRRRRRRR....", "....RRRRRRRR....",
  "....RRRRRRRR....", ".....RRRRRR.....", ".....RRRRRR....."])
# hot chocolate mug with steam and molinillo
H['hot_chocolate'] = pad(["...W....W.......", "....W....W......", "...W....W...T...", "....W....W.TT...", "..........T.....",
  ".SSSSSSSSTSS....", ".SNNNNNNTNNS....", ".SSSSSSSSSSSSS..", ".SSSSSSSSSSS..S.", ".SSWSSSSSSSS..S.", ".SSSSSSSSSSS..S.",
  ".SSSSSSSSSSSSS..", ".SSSSSSSSSSS....", "..SSSSSSSSS.....", "................", "................"])
# beans: individual beans in a clay bowl, with steam
g = grid()
for y,r in enumerate(["....W....W......", ".....W....W.....", "....W....W......", "................",
    "......NN.NN.....", "...NN.RR.NN.NN..", "..RR.NN.NN.RR.N.", ".NN.RR.NN.RR.NN.",
    "OOOOOOOOOOOOOOOO", ".OOOOOOOOOOOOOO.", ".OOYOOYOOYOOYOO.", "..OOOOOOOOOOOO..", "...OOOOOOOOOO...", ".....OOOOOO....."]):
    for x,c in enumerate(r):
        if c != '.': g[1+y][x] = c
H['beans'] = done(g)
B.PAL['b'] = (0, 9, 30)   # dim sky, ~15% duty background for the monarch
# pinata: 6 cones round a centre, streamers hanging from the lower tips
H['pinata'] = ['.......PP.......', '.......PP.......', '..RR..PPPP..gg..', '..RRR.PPPP.ggg..', '...RRRYYYYggg...', '....RYYYYYYg....', '....YYYYYYYY....', '....YYYYYYYY....', '....OYYYYYYS....', '...OOOYYYYSSS...', '..OOO.UUUU.SSS..', '..OO..UUUU..SS..', '..Yg...UU...gY..', '..PS...UU...SP..', '..Yg...gY...gY..', '..PS...PS...SP..']
# maracas: two straight, side by side
g = grid()
for cx, c in ((3.5, 'R'), (11.5, 'g')):
    for y in range(16):
        for x in range(16):
            if (x-cx)**2 + ((y-4)*1.1)**2 <= 3.4**2: g[y][x] = 'Y' if y == 4 else c
    for y in range(8, 16):
        g[y][int(cx)] = g[y][int(cx)+1] = 'N'
H['maracas'] = done(g)
# torogoz: green-turquoise bird, rufous chest, racket tail
H['torogoz'] = pad(["", "....SSSS........", "...SggggS.......", "..ggWKgggg......", "YYggKKgggg......", "..OggggggSS.....",
  "...OOOggSSSS....", "...OOOOgSSSS....", "....OOOgSSSS....", ".....OOgSSS.....", "NNNNNNNNNSSNNNN.", "..........S.....",
  "...........S....", "............S...", ".............SS.", ".............SS."])
# monarch, after the user's reference: orange upper / yellow-orange lower wings,
# black border, veins, body and antennae as negative space on a dim sky
half = ["bbbbb.bb", "....bb.b", "W.....b.", ".OOOO...", ".OOOOOO.", "W.O.OOO.", ".OOO.OO.", "b.OOOOO.",
        "bb...OO.", "b.YYYYY.", ".YYY.YY.", "W.YYY.Y.", ".YYYYY..", "b.W...b.", "bbb...bb", "bbbbbbbb"]
H['monarch'] = [r + r[::-1] for r in half]
for n in ('tortillas','mango','tamal'): H.pop(n)
for n,rows in H.items():
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), n
    B.I[n] = dict(set='heritage', rows=rows)
outj = {n: dict(set='heritage', key=B.keyfor([r]), rows=r) for n,r in H.items()}
json.dump(outj, open(os.path.join(OUT, 'heritage.json'), 'w'), indent=1)
B.sheet('heritage', 'heritage.jpg')
