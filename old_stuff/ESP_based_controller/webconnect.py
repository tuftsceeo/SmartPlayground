import sys
import uselect
import time
import servo
import json
import ssd1306
from machine import Pin, SoftI2C, PWM, ADC, Timer

serialPoll = uselect.poll()
serialPoll.register(sys.stdin, uselect.POLLIN)

i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
display = ssd1306.SSD1306_I2C(128, 64, i2c)

display.text("HELLO!", 40,35,1)
display.show()

# connect light 
light = ADC(Pin(5))
light.atten(ADC.ATTN_11DB)

# connect servo
motor = servo.Servo(Pin(2))
motor.write_angle(90)

# this is the dynamic training data 
training_data = []
datafilename = "trainData.txt"

STATE = 0
NN_index = 0
global_TEST_motor = 0

switch_state_select = False
last_switch_state_select = False
switched_select = False

# select switch
switch_select = Pin(9, Pin.IN)

run_manual = False 

def readSensor():
    l=[]
    for i in range(1000):
        l.append(light.read())
    l.sort()
    l=l[300:600]
    avlight=sum(l)/len(l)
    
    point = avlight
    return int(point)

# saves training_data to a file trainData.txt
# each line is motorData,lightSensor
def saveDataToFile():
    f=open("trainData.txt","w")
    length = len(training_data)
    for ind, val in enumerate(training_data):
        lightSensor = val[1]
        motor_val = val[0]
        f.write(str(motor_val))
        f.write(",")
        f.write(str(lightSensor))
        f.write('\n')
    f.close()

# Adds data to the local memory
def add_pair(motor, light):
    tup = (int(motor), int(light))
    global training_data
    training_data.append(tup)

def removeData(i):
    global training_data
    if(len(training_data) != 0):
        training_data.pop(i)

def readSerial():
    """
    reads a single character over serial.

    :return: returns the character which was read, otherwise returns None
    """
    return(sys.stdin.read(1) if serialPoll.poll(0) else None)

# Handles explore mode of json dict 
def explore(json_obj):

    dict_obj = {}
    if("m" in json_obj):
        global motor
        motor.write_angle(180-int(json_obj["m"]))
    t = readSensor()
    sensor_val = int((100 * int(t))/4095)
    dict_obj["s"] = sensor_val
    
    string = json.dumps(dict_obj)
    sys.stdout.write(string+"\n")
    
def train(json_obj):

    dict_obj = {}
    if("m" in json_obj):
        global motor
        motor.write_angle(180-int(json_obj["m"]))
    t = readSensor()
    sensor_val = int((100 * int(t))/4095)
    dict_obj["s"] = sensor_val
    
    # check if adding or deleting a value
    if ("am" in json_obj and "as" in json_obj):
        # add this value
        add_motor = int(json_obj["am"])
        light = int(json_obj["as"])
        add_pair(add_motor, light)
        saveDataToFile()
    
    if("di" in json_obj):
        # delete this index
        index = int(json_obj["di"])
        removeData(index)
        saveDataToFile()
        
    string = json.dumps(dict_obj)
    sys.stdout.write(string+"\n")

def runData():
    sens = readSensor()
    sens = int((100 * int(sens))/4095)
    light_val = []
    motor_val = []
    if(len(training_data) > 0):
        for (mot, light) in training_data:
            dist = abs(sens - light)
            light_val.append(dist)
            motor_val.append(mot)
        # get the index of the least light_val
        global NN_index
        NN_index = light_val.index(min(light_val))
        pos = motor_val[NN_index]
        global global_TEST_motor
        global_TEST_motor = pos
        
        global motor
        motor.write_angle(180-pos)

def play(json_obj):

    dict_obj = {}
    t = readSensor()
    sensor_val = int((100 * int(t))/4095)
    dict_obj["s"] = sensor_val
    global STATE
    if("r" in json_obj):
        # stop runData
        if(int(json_obj["r"]) == 0):
            STATE = 0
        
        # start runData   
        elif(int(json_obj["r"]) == 1):
            STATE = 1
            
    if(STATE == 1):
        runData()
        dict_obj["m"] = global_TEST_motor
        dict_obj["i"] = NN_index
        
    string = json.dumps(dict_obj)
    sys.stdout.write(string+"\n")

# New function for displaying current values in text file 
# reads the file where each line is the motor,light data
# To avoid an error: If trainData.txt is empty make sure starts with line 1 
def onload():
    global training_data
    training_data = []
    with open("trainData.txt", "r") as values:
        lines = values.readlines()
    motor_list = []
    sensor_list = []
    dict_obj = {}
    if (len(lines) > 0):
        for l in lines:
            as_list = l.split(",")
            motor= as_list[0]
            light = as_list[1].split('\n')[0]
            add_pair(int(motor), int(light))
            motor_list.append(int(motor))
            sensor_list.append(int(light))
    dict_obj["m"] = motor_list
    dict_obj["s"] = sensor_list
             
    string = json.dumps(dict_obj)
    sys.stdout.write(string+"\n")
    
    
def handleJson(string):
    json_obj = json.loads(string)
    # turn off play if on the Explore or Train page 
    if(json_obj["st"] == "e" or json_obj["st"] == "t"):
        global STATE
        STATE = 0
    # explore mode
    if(json_obj["st"] == "e"):
        explore(json_obj)
    # train mode 
    elif(json_obj["st"] == "t"):
        train(json_obj)
    # play mode 
    elif(json_obj["st"] == "p"):
        play(json_obj)
        
    elif(json_obj["st"] == "l"):
        onload()

final_string = ''
append = False

starttime = time.time()
timer_begin = False

def selectpressed():
    #declare all global variables, include all flags
    global run_manual
    if(run_manual == False):
        run_manual = True
    else:
        run_manual = False

def selectNotpressed():
    if(run_manual == True):
        display.fill(0)
        display.text("NOT clicked", 25,35,1)
        display.show()

def check_switch(p):
    global switch_state_select
    global switched_select
    global last_switch_state_select

    switch_state_select = switch_select.value()
         
    if switch_state_select != last_switch_state_select:
        switched_select = True
        
    if switched_select:
        if switch_state_select == 0:
            selectpressed()
        switched_select = False
        #time.sleep(0.1)
    
    #if(switched_select == False):
    #    selectNotpressed()
        
    last_switch_state_select = switch_state_select

#setting up Timers
tim = Timer(0)
tim.init(period=50, mode=Timer.PERIODIC, callback=check_switch)

while True:
    if(run_manual == False):
        # continuously read commands over serial and handles them
        message = readSerial()
        # start of json dict
        if(message == '{'):
            append = True 

        # end of json dict
        elif(message == '}'):
            append = False
            final_string += message
            handleJson(final_string)
            final_string = ""
            
        if(append):
            if(type(message) is str):
                final_string += message
                
        if(message == None and timer_begin == False):
            starttime = time.time()
            timer_begin = True
        elif(not message is None):
            if(timer_begin):
                display.fill(0)
                display.text("Connected!", 25,35,1)
                display.show()
                timer_begin = False
        
        if(timer_begin == True and time.time()-starttime > 1):
            display.fill(0)
            display.text("Device", 30,15,1)
            display.text("Not", 30,35,1)
            display.text("Connected", 30,55,1)
            display.show()
    else:
        display.fill(0)
        display.text("PLAY MODE",30,35,1)
        display.show()
        if(len(training_data) == 0):
            onload()
        runData()
