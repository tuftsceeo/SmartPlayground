#servo code example
# does not include espnow communication

import machine

import time

# Create a regular p23 GPIO object
p18 = machine.Pin(18, machine.Pin.OUT)

# Create another object named pwm by
# attaching the pwm driver to the pin
pwm = machine.PWM(p18)

# Set the pulse every 20ms
pwm.freq(50)

# Set initial duty to 0
# to turn off the pulse
pwm.duty(0)

# Creates a function for mapping the 0 to 180 degrees
# to 20 to 120 pwm duty values
def map(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

# Creates another function for turning 
# the servo according to input angle
def servo(pin, angle):
    pin.duty(map(angle, 0, 180, 20, 120))

'''
#sets servo position
servo(pwm, 0)


servo(pwm, 90) 


servo(pwm, 180)
'''

# rotates servo


'''
for i in range(45, 91, 10):
    servo(pwm, i)
    time.sleep(0.1)
time.sleep(1)

for i in range(90, 44, -10): #(start, end, interval)
    servo(pwm, i)
    time.sleep(0.1) #(0.01 for smooth rotation)
'''

def A():
    for i in range(45, 91, 10):
        servo(pwm, i)
        time.sleep(0.1)
    time.sleep(1)

    for i in range(90, 44, -10): #(start, end, interval)
        servo(pwm, i)
        time.sleep(0.1) #(0.01 for smooth rotation)
    time.sleep(1)
    
    
while True:
    A()

