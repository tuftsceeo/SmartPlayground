import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont
OUT = os.path.dirname(os.path.abspath(__file__))
PAL = dict(W=(255,171,93), L=(180,120,65), G=(110,74,40), K=(30,20,10), Y=(255,150,0), O=(255,60,0),
  R=(255,0,0), g=(20,160,0), D=(0,100,0), B=(0,0,255), S=(0,60,200), U=(100,0,255), N=(150,45,5),
  E=(80,20,0), P=(255,94,50), T=(180,60,10), C=(255,140,60),
  j=(178,105,0), V=(180,30,255))  # V = light purple highlight  # j = yellow at 70% duty (flicker dim)
def mirror(rows):  # rows given as left 8 chars -> mirrored 16
    return [r + r[::-1] for r in rows]
def shift(rows, dy):
    blank = '.'*16
    return (rows[dy:] + [blank]*dy) if dy > 0 else ([blank]*(-dy) + rows[:dy])
I = {}
# ---------- HALLOWEEN ----------
pump = [
"........DD......",
".......DD.......",
"...OOOOEEOOOO...",
"..OOOOOOOOOOOO..",
".OOOOOOOOOOOOOO.",
".OOOOOOOOOOOOOO.",
"OOOOYOOOOOOYOOOO",
"OOOYYYOOOOYYYOOO",
"OOYYYYYOOYYYYYOO",
"OOOOOOOYYOOOOOOO",
"OYYOOOOOOOOOOYYO",
"OOYYYYOYYOYYYYOO",
".OOYYYYYYYYYYOO.",
".OOOYYYOOYYYOOO.",
"..OOOOOOOOOOOO..",
"....OOOOOOOO....",
]
I['jack_o_lantern'] = dict(set='halloween', fps=6, frames=[pump, [r.replace('Y','W') for r in pump], [r.replace('Y','j') for r in pump], pump])
def bat(half):
    rows=['.'*8]*16
    for y,r in half.items(): rows[y]=r
    return mirror(rows)
up   = {1:"U.......",2:"UU......",3:"UUU.....",4:"UUUU..U.",5:"UUUUUUUU",6:"U.UUUUYU",7:"...U.UUU",8:"......UU",9:"......UU",10:"......UU",11:".......U"}
level= {4:"......U.",5:"..UUUUUU",6:".UUUUUYU",7:"UUUUUUUU",8:"U.UU.UUU",9:"U..U..UU",10:"......UU",11:".......U"}
down = {4:"......U.",5:".....UUU",6:"....UUYU",7:"...UUUUU",8:"..UUUUUU",9:".UUUUUUU",10:"UU.UU.UU",11:"U..U...U",12:"U......."}
I['bat'] = dict(set='halloween', fps=6, frames=[bat(up), bat(level), bat(down), bat(level)])
I['skull'] = dict(set='halloween', rows=[
"................",
".....WWWWWW.....",
"...WWWWWWWWWW...",
"..WWWWWWWWWWWW..",
".WWWWWWWWWWWWWW.",
".WWKKKWWWWKKKWW.",
".WKKKKKWWKKKKKW.",
".WKKKKKWWKKKKKW.",
".WWKKKWWWWKKKWW.",
"..WWWWWKKWWWWW..",
"..WWWWKKKKWWWW..",
"...WWWWWWWWWW...",
"....WKWKWKWKW...",
"....WKWKWKWKW...",
".....WWWWWWW....",
"................"])
I['candy'] = dict(set='halloween', rows=mirror([
"........",
"........",
"........",
"........",
"Y...RRRR",
"YY.RRWWR",
"YYYRWWRR",
"YYYRRRRW",
"YYYRRRRW",
"YYYRWWRR",
"YY.RRWWR",
"Y...RRRR",
"........",
"........",
"........",
"........"]))
gh = [
"................",
".....WWWWWW.....",
"...WWWWWWWWWW...",
"..WWWWWWWWWWWW..",
"..WWWWWWWWWWWW..",
".WWWKKWWWWKKWWW.",
".WWWKKWWWWKKWWW.",
".WWWKKWWWWKKWWW.",
".WWWWWWWWWWWWWW.",
".WWWWWWKKWWWWWW.",
".WWWWWWKKWWWWWW.",
".WWWWWWWWWWWWWW.",
".WWWWWWWWWWWWWW.",
".WWWWWWWWWWWWWW.",
".WWW..WWWW..WWW.",
".WW....WW....WW."]
gh2 = shift(gh[:14], 1)[:0] + gh[1:14] + [".W..WWW..WWW..W.", "................", "................"]
gh2 = gh2[:16]
I['ghost'] = dict(set='halloween', fps=3, frames=[gh, gh2])
I['witch_hat'] = dict(set='halloween', rows=[
"............UU..",
"..........UUU...",
"........UUUU....",
".......UUU......",
"......UUUU......",
"......UUUU......",
".....UUUUUU.....",
".....UUUUUU.....",
"....UUUUUUUU....",
"....OOYYYYOO....",
"....OOYKKYOO....",
"....OOYYYYOO....",
".UUUUUUUUUUUUUU.",
"UUUUUUUUUUUUUUUU",
"................",
"................"])
I['spider'] = dict(set='halloween', rows=mirror([
".......W",
".......W",
".......W",
"......UU",
".V..UUUU",
"V.V.UUUU",
"V..VUWKU",
".V.VUKKU",
".VVVUUUU",
"V..VUUUU",
"V.VVUKUU",
".V.VUUKK",
".V..UUUU",
"V..V.UUU",
"V.V.....",
"........"]))
I['candy_corn'] = dict(set='halloween', rows=[
".......WW.......",
"......WWWW......",
"......WWWW......",
".....WWWWWW.....",
".....OOOOOO.....",
"....OOOOOOOO....",
"....OOOOOOOO....",
"...OOOOOOOOOO...",
"...OOOOOOOOOO...",
"..YYYYYYYYYYYY..",
"..YYYYYYYYYYYY..",
".YYYYYYYYYYYYYY.",
".YYYYYYYYYYYYYY.",
".YYYYYYYYYYYYYY.",
"..YYYYYYYYYYYY..",
"................"])
pot = [
"................",
"................",
"................",
"..ggggggggggggg.",
".LLLLLLLLLLLLLL.",
"..GGGGGGGGGGGG..",
".GGGGGGGGGGGGGG.",
".GGGGGGGGGGGGGG.",
".GGGGGGGGGGGGGG.",
".GGGGGGGGGGGGGG.",
".GGGGGGGGGGGGGG.",
"..GGGGGGGGGGGG..",
"...GGGGGGGGGG...",
"..O.GG.YY.GG.O..",
".OYO.OYOOYO.OYO.",
"OYYYOYYYYYYOYYYO"]
pot = [r.replace("L","W").replace("G","L") for r in pot]
pot = [pot[0], pot[1], pot[2], "...gggggggggg...", *pot[4:]]
def bubbles(p, pts):
    g = [list(r) for r in p]
    for x,y in pts: g[y][x] = 'g'
    return [''.join(r) for r in g]
I['cauldron'] = dict(set='halloween', fps=3, frames=[bubbles(pot,[(5,2),(6,2),(11,2),(9,0)]), bubbles(pot,[(5,1),(6,1),(10,2),(11,2),(8,2)]), bubbles(pot,[(4,0),(10,1),(11,1),(7,2),(8,2)])])
I['monster'] = dict(set='halloween', rows=[
"..NNNNNNNNNNNN..",
".NNNNNNNNNNNNNN.",
".NNNNNNNNNNNNNN.",
".gggKgggggggKgg.",
".gggggggggggggg.",
".ggKKKggggKKKgg.",
"Lggggggggggggggl",
"LggWWWggggWWWggL",
"LggWKWggggWKWggL",
".gggggggggggggg.",
".gggggggggggggg.",
".ggKKKKKKKKKKgg.",
".gggKggKggKgggg.",
".gggggggggggggg.",
"..gggggggggggg..",
"................"])
I['monster']['rows'][6] = "LggggggggggggggL"
# ---------- MUERTOS ----------
I['calavera'] = dict(set='muertos', rows=[
"....WWWWWWWW....",
"..WWWWWSSWWWWW..",
".WWWWWSYYSWWWWW.",
".WWWWWWSSWWWWWW.",
"WWPPPPWWWWPPPPWW",
"WWPKKPWWWWPKKPWW",
"WWPKKPWWWWPKKPWW",
"WWPPPPWWWWPPPPWW",
"WgWWWWWKKWWWWWgW",
"WWgWWWWKKWWWWgWW",
".WWWWWWWWWWWWWW.",
"..WKKKKKKKKKKW..",
"..WWKWKWKWKWWW..",
"...WWWWWWWWWW...",
".....WWWWWW.....",
"................"])
I['marigold'] = dict(set='muertos', rows=[
"....O.OO.O......",
"..OOYOOYOOYO....",
".OYOOYOOOYOOO...",
"OOOYOOOYOOOYOO..",
".OYOOYOYOYOOYO..",
"OOOYOOYOOOYOOOO.",
".OYOOOYOYOOYOO..",
"..OOYOOOOYOOO...",
"....OOYOOO......",
"......DD........",
"..ggg.DD........",
".ggggDDD...ggg..",
"..gggDD...gggg..",
"......DDggggg...",
"......DD.ggg....",
"......DD........"])
# shift marigold right by 1 for centring
I['marigold']['rows'] = ['.' + r[:15] for r in I['marigold']['rows']]
flag = ["XXXXXXX","XXX.XXX","XX...XX","XXX.XXX","XXXXXXX","X.XXX.X","XXXXXXX","XX.X.XX","XXXXXXX","X.X.X.X"]
g=[['.']*16 for _ in range(16)]
for x in range(16): g[2][x]='W'
for x0,c in ((0,'P'),(9,'g')):
    for y,r in enumerate(flag):
        for i,ch in enumerate(r):
            if ch=='X': g[3+y][x0+i]=c
for y,r in enumerate(flag[:6]):  # peeking third colour between? (none)
    pass
I['papel_picado'] = dict(set='muertos', rows=[''.join(r) for r in g])
cbase = [
".......EE.......",
".....WWWWWW.....",
".....WWWWWWL....",
".....WWWWWWL....",
".....WWWWWLL....",
".....WWWWWWL....",
".....WWWWWWL....",
".....WWWWWWL....",
"...NNNNNNNNNN...",
"..NNNNNNNNNNNN..",]
def candle(fl): return fl[1:] + cbase
fA = ["................",".......YY.......","......OYYO......","......OYYO......",".....OYWWYO.....",".....OYWWYO.....","......OYYO......"]
fB = ["................","......YY........",".....OYYO.......","......OYYO......",".....OYWWYO.....",".....OYWWYO.....","......OYYO......"]
fC = ["................","........YY......",".......OYYO.....","......OYYO......",".....OYWWYO.....",".....OYWWYO.....","......OYYO......"]
I['ofrenda_candle'] = dict(set='muertos', fps=5, frames=[candle(fA), candle(fB), candle(fA), candle(fC)])
I['pan_de_muerto'] = dict(set='muertos', rows=[
"................",
"................",
".......YY.......",
"......YWYY......",
"....OOOYYOOO....",
"...OOYOOOOYOO...",
"..OWOOYOOYOOWO..",
".OOOOOOYYOOOOOO.",
".OOOOOYYYYOOOOO.",
"OOWOOYOOOOYOOWOO",
"OOOOYOOWOOOYOOOO",
"OOOYOOOOOOWOYOOO",
".OYOOWOOOOOOOYO.",
"..OOOOOOOOOOOO..",
"................",
"................"])


# ---------- EYES IN THE DARK ----------
def eyes(pupil_cols, pupil_rows=(6,7,8,9), shape=(".YYYY.","YYYYYY","YYYYYY",".YYYY."), top=6):
    g=[['.']*16 for _ in range(16)]
    for x0 in (1,9):
        for i,r in enumerate(shape):
            for j,c in enumerate(r):
                if c!='.': g[top+i][x0+j]=c
        for y in pupil_rows:
            for px in pupil_cols:
                if g[y][x0+px]!='.': g[y][x0+px]='K'
    return [''.join(r) for r in g]
C_=eyes((2,3)); L_=eyes((0,1)); R_=eyes((4,5)); U_=eyes((2,3),(6,7))
HALF=eyes((2,3),(7,8),shape=("......","YYYYYY",".YYYY.","......"))
SHUT=eyes((),(),shape=("......","......","YYYYYY","......"))
I['eyes'] = dict(set='halloween', fps=3, frames=[C_,C_,L_,C_,R_,C_,U_,C_,HALF,SHUT])
# ---------- TEXT ----------
F5 = dict(T=["XXXXX"]+["..X.."]*6, R=["XXXX.","X...X","X...X","XXXX.","X.X..","X..X.","X...X"],
 I=[".XXX."]+["..X.."]*5+[".XXX."], C=[".XXX.","X...X","X....","X....","X....","X...X",".XXX."],
 K=["X...X","X..X.","X.X..","XX...","X.X..","X..X.","X...X"], O=[".XXX."]+["X...X"]*5+[".XXX."],
 E=["XXXXX","X....","X....","XXXX.","X....","X....","XXXXX"], A=[".XXX.","X...X","X...X","XXXXX","X...X","X...X","X...X"],
 P=["XXXX.","X...X","X...X","XXXX.","X....","X....","X...."], L=["X...."]*6+["XXXXX"],
 S=[".XXXX","X....","X....",".XXX.","....X","....X","XXXX."], N=["X...X","XX..X","X.X.X","X.X.X","X..XX","X...X","X...X"])
F3 = dict(T=["XXX",".X.",".X.",".X.",".X."], R=["XX.","X.X","XX.","X.X","X.X"], I=["XXX",".X.",".X.",".X.","XXX"],
 C=[".XX","X..","X..","X..",".XX"], K=["X.X","X.X","XX.","X.X","X.X"], O=["XXX","X.X","X.X","X.X","XXX"],
 E=["XXX","X..","XX.","X..","XXX"], A=[".X.","X.X","XXX","X.X","X.X"], P=["XX.","X.X","XX.","X..","X.."],
 L=["X..","X..","X..","X..","XXX"], S=[".XX","X..",".X.","..X","XX."], N=["X.X","XXX","XXX","X.X","X.X"])
def strip(text, font, h, col):
    cols=[]
    for ch in text:
        if ch==' ': cols += [['.']*h]*3; continue
        gl=font[ch]
        for x in range(len(gl[0])): cols.append([col if gl[y][x]=='X' else '.' for y in range(h)])
        cols.append(['.']*h)
    return cols
def marquee(text, col, top=4):
    cols = [['.']*7]*16 + strip(text, F5, 7, col) + [['.']*7]*15
    frames=[]
    for off in range(len(cols)-15):
        g=[['.']*16 for _ in range(16)]
        for x in range(16):
            for y in range(7): g[top+y][x]=cols[off+x][y]
        frames.append([''.join(r) for r in g])
    return frames
def words(lines, col):  # lines: list of 1-2 strings, 3x5 font, centred
    g=[['.']*16 for _ in range(16)]
    tops = [5] if len(lines)==1 else [2,9]
    for t,line in zip(tops, lines):
        c = strip(line, F3, 5, col)[:-1]
        x0 = (16-len(c))//2
        for x,colm in enumerate(c):
            for y in range(5): g[t+y][x0+x]=colm[y]
    return [''.join(r) for r in g]
I['trick_or_treat'] = dict(set='text', fps=10, sheet_step=8, frames=marquee("TRICK OR TREAT",'O'))
I['please_take_one'] = dict(set='text', fps=10, sheet_step=8, frames=marquee("PLEASE TAKE ONE",'W'))
I['trick_or_treat_words'] = dict(set='text', fps=1, frames=[words(["TRI","CK"],'O'), words(["OR"],'O'), words(["TRE","AT"],'O')])
I['please_take_one_words'] = dict(set='text', fps=1, frames=[words(["PLE","ASE"],'W'), words(["TAKE"],'W'), words(["ONE"],'W')])

F6 = dict(T=["XXX"]+[".X."]*5, A=[".X.","X.X","X.X","XXX","X.X","X.X"], K=["X.X","X.X","XX.","XX.","X.X","X.X"],
 E=["XXX","X..","XX.","X..","X..","XXX"], O=["XXX","X.X","X.X","X.X","X.X","XXX"], N=["X..X","XX.X","XX.X","X.XX","X.XX","X..X"])
def put(g, text, font, h, top, x0, col):
    c = strip(text, font, h, col)[:-1]
    if x0 is None: x0 = (16-len(c))//2
    for x,colm in enumerate(c):
        for y in range(h): g[top+y][x0+x]=colm[y]
def blank(): return [['.']*16 for _ in range(16)]
g=blank(); put(g,"TAKE",F3,5,2,None,'W'); put(g,"ONE",F3,5,10,None,'O')
I['take_one'] = dict(set='text2', rows=[''.join(r) for r in g])
g=blank(); put(g,"TAKE",F6,6,1,None,'W'); put(g,"ONE",F6,6,9,None,'O')
I['take_one_bold'] = dict(set='text2', rows=[''.join(r) for r in g])
g=blank(); put(g,"TAKE",F6,6,1,None,'W'); put(g,"ONE",F6,6,9,0,'O')
for y,r in enumerate(["Y..Y","YRRY","Y..Y"]):
    for x,c in enumerate(r):
        if c!='.': g[11+y][12+x]=c
# candy: wrapper ends Y, red middle
I['take_one_candy'] = dict(set='text2', rows=[''.join(r) for r in g])

# ---------- checks / output ----------
for n,d in I.items():
    for f in d.get('frames',[d.get('rows')]):
        assert len(f)==16 and all(len(r)==16 for r in f), (n,[len(r) for r in f])
        for r in f:
            for c in r: assert c=='.' or c in PAL, (n,c)
def keyfor(frames):
    used = sorted({c for f in frames for r in f for c in r} - {'.'})
    return {c: list(PAL[c]) for c in used}
outj = {}
for n,d in I.items():
    fr = d.get('frames') or [d['rows']]
    e = dict(set=d['set'], key=keyfor(fr))
    if 'frames' in d: e['fps']=d['fps']; e['frames']=d['frames']
    else: e['rows']=d['rows']
    outj[n]=e
json.dump(outj, open(os.path.join(OUT,'holiday.json'),'w'), indent=1)
# LED->screen model (port of display.js ledScreenRgb)
PRIM = [(0.7006,0.2993,400),(0.0743,0.8338,1150),(0.1241,0.0578,250)]
PRIM = [((x/y)*Iv, Iv, ((1-x-y)/y)*Iv) for x,y,Iv in PRIM]
LY = sum(p[1] for p in PRIM)
def scr(d):
    X,Y,Z = [sum(d[j]/255*PRIM[j][i] for j in range(3))/LY for i in range(3)]
    out=[]
    for c in (3.2406*X-1.5372*Y-0.4986*Z, -0.9689*X+1.8758*Y+0.0415*Z, 0.0557*X-0.204*Y+1.057*Z):
        v=max(0,min(1,c)); out.append(round((12.92*v if v<=0.0031308 else 1.055*v**(1/2.4)-0.055)*255))
    return tuple(out)
CELL=16
def render(rows):
    im = Image.new('RGB',(16*CELL+8,16*CELL+8),(12,12,12)); dr=ImageDraw.Draw(im)
    for y,r in enumerate(rows):
        for x,c in enumerate(r):
            col = scr(PAL[c]) if c!='.' else (24,24,24)
            dr.rectangle([4+x*CELL+1,4+y*CELL+1,4+x*CELL+CELL-2,4+y*CELL+CELL-2],fill=col)
    return im
try: font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 20)
except Exception: font = ImageFont.load_default()
def sheet(setname, fname, labels=True):
    items = [(n,d) for n,d in I.items() if d['set']==setname]
    tw = 264; pad=24
    rowsz = []
    for n,d in items: rowsz.append(len(d.get('frames',[0])))
    # layout: each icon a row block; statics packed 4 per row, animated on own row
    blocks=[]; cur=[]
    for n,d in items:
        if 'frames' in d:
            if cur: blocks.append(cur); cur=[]
            st=d.get('sheet_step',1); fl=[(f"{n}  f{i+1}", f) for i,f in enumerate(d['frames']) if i%st==0]
            for k in range(0,len(fl),4): blocks.append(fl[k:k+4])
        else:
            cur.append((n if labels else f"#{list(I).index(n)}", d['rows']))
            if len(cur)==4: blocks.append(cur); cur=[]
    if cur: blocks.append(cur)
    W = pad + 4*(tw+pad); H = pad + len(blocks)*(tw+40+pad)
    im = Image.new('RGB',(W,H),(0,0,0)); dr=ImageDraw.Draw(im)
    for bi,b in enumerate(blocks):
        for i,(lab,rows) in enumerate(b):
            x = pad + i*(tw+pad); y = pad + bi*(tw+40+pad)
            dr.text((x,y),lab,fill=(230,230,230),font=font)
            im.paste(render(rows),(x,y+32))
    im.save(os.path.join(OUT,fname),quality=92)
sheet('halloween','halloween.jpg'); sheet('muertos','muertos.jpg'); sheet('text','text.jpg'); sheet('text2','take_one.jpg')
if len(sys.argv)>1:
    sheet('halloween','blind_h.jpg',False); sheet('muertos','blind_m.jpg',False)
for n,d in I.items():
    if 'frames' in d:
        fr=[render(f) for f in d['frames']]
        fr[0].save(os.path.join(OUT,f'{n}.gif' if n!='eyes' else 'eyes.gif'),save_all=True,append_images=fr[1:],duration=int(1000/d['fps']),loop=0)
print('ok', len(I))
