import os
def rm(p):
    try:
        os.remove(p)
    except OSError:
        pass
for f in os.listdir('/lib'):
    if f.endswith('.mpy'):
        rm('/lib/' + f[:-4] + '.py')
rm('/wand_main.py')
with open('/main.py', 'w') as fh:
    fh.write('import time\nprint("5 second grace")\ntime.sleep(5)\n\nimport wand_main\n')
print('lib:', sorted(os.listdir('/lib')))
print('root:', sorted(os.listdir('/')))
