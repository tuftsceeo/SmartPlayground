from BLE_CEEO import Yell
import time
from hub import port
import motor

motors =[port.A, port.C]

'''
Small motor (essential): -660 to 660
Medium motor: -1110 to 1110
Large motor: -1050 to 1050
'''
def drive(speed):
    for m in motors: 
        motor.run(m, speed)
        
def peripheral(name): 
    try:
        p = Yell(name, verbose = True)
        if p.connect_up():
            print('P connected')
            while True:
                if p.is_any:
                    cmd = p.read()
                    print(cmd)
                    if 'fwd' in cmd:
                        drive(500)
                    if 'back' in cmd:
                        drive(-500)
                if not p.is_connected:
                    print('lost connection')
                    break
                time.sleep(0.5)
    except Exception as e:
        print(e)
    finally:
        p.disconnect()
        drive(0)
        print('closing up')
        
peripheral('Maria')
