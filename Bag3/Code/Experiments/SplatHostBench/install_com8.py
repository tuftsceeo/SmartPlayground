import os
def rm(p):
    try:
        os.remove(p)
    except OSError:
        pass
for f in os.listdir('/benchmpy'):
    if f == 'wand_main.mpy':
        dst = '/wand_main.mpy'
    else:
        dst = '/lib/' + f
        rm('/lib/' + f[:-4] + '.py')
    rm(dst)
    os.rename('/benchmpy/' + f, dst)
rm('/wand_main.py')
rm('/main.py.bak')
with open('/main.py', 'w') as fh:
    fh.write('import time\nprint("5 second grace")\ntime.sleep(5)\n\nimport wand_main\n')
print('lib:', sorted(os.listdir('/lib')))
print('root:', [f for f in os.listdir('/') if f.endswith(('.py', '.mpy', '.txt', '.json'))])
