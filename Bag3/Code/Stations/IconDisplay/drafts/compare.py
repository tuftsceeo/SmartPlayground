import heritage, build as B
D='/Users/jcross04/Documents/GitHub/SmartPlayground/Bag3/Code/Stations/IconDisplay/icons/'
for n,d in list(B.I.items()):
    if d['set']=='heritage': B.I[n]=dict(set='compare',rows=d['rows'])
for n in ('cookie','pizza','icecream','butterfly','parrot','banana'):
    ns={}; exec(open(D+n+'.py').read(),ns); t=ns['ICON']; keys={}; rows=[]
    for y in range(16):
        r=''
        for x in range(16):
            c=tuple(t[y*16+x]); r+='.' if c==(0,0,0) else keys.setdefault(c,chr(0x100+len(keys)))
        rows.append(r)
    for c,k in keys.items(): B.PAL[k]=c
    B.I['OLD '+n]=dict(set='compare',rows=rows)
B.sheet('compare','foods_compare.jpg')
