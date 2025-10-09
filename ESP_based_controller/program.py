
#SmartMotors code
#Last Edited : Jan 12, 2024
#Code by Milan Dahal
#Sensors to the left of the hub
#Motors to the right of the hub
# you can choose your SM sensor motor pair - supports multiple SM pairs in one hub


import hub
import motor
import device
import time
import math
from hub import button, sound , light_matrix
from hub import light as rgb
buttonPressed=button.pressed
Run=button.RIGHT
Data=button.LEFT
deleteData=button.CONNECT


deviceTypeLookup={48:'M',49:'M',65:'M',61:'S',62:'S',63:'S',255:'N'}

SMModes="" # SS, MS


def blink():

        for i in range(5):
            ypos=[]
            for j in range(5):
                if(light_matrix.get_pixel(i,j)==100):
                    ypos.append(j)
            for y in ypos:
                light_matrix.set_pixel(i,y,0)
            time.sleep(0.08)
            for y in ypos:
                light_matrix.set_pixel(i,y,100)


#defining tones/tunes for different actions
startTone=[[740,100],[587,100],[440,100],[293,100],[740,100],[587,100],[440,100],[293,50]]
saveTone=[[493,100]]
runTone=[[293,100],[440,100],[587,100],[740,50]]
trainTone=[[740,100],[587,100],[440,100],[293,50]]
newconnectTone=[[293,50],[1,150],[293,30]]
shutDown=[[740,100],[587,100],[440,100],[293,100],[740,100],[587,100],[440,100],[293,50]]

def playmusic(music):
    for d in music:
        sound.beep(d[0])
        time.sleep_ms(d[1])
        


class Connections:
    def __init__(self):
        self.deviceType=[0]*6
        self.temp = [0] * 25
        self.pairs=[]

        self.ReadPorts()

    def ReadPorts(self):
        #self.deviceType = [deviceTypeLookup[device.id(i)] for i in range(6) if device.ready(i) else 'None']
        tempdeviceType=[0]*6
        for i in range(6):
            if device.ready(i):
                tempdeviceType[i] = deviceTypeLookup[device.id(i)]
            else:
                tempdeviceType[i]=None

        self.numberOfMotors = self.deviceType.count('M')
        self.numberOfSensors = self.deviceType.count('S')
        self.locationOfSensors = [i for i in range(len(self.deviceType)) if self.deviceType[i] == 'S']
        self.locationOfMotors =[i for i in range(len(self.deviceType)) if self.deviceType[i] == 'M']
        print(self.deviceType, tempdeviceType)
        
        if(not tempdeviceType==self.deviceType):
            print("play tone")
            playmusic(newconnectTone)
            self.deviceType=tempdeviceType

    def ShowAllConnections(self):
        self.temp = [0] * 25
        self.pairs=[]

        #find what is connected to the ports
        self.ReadPorts()

        if(self.numberOfSensors==1 and self.locationOfSensors[0]%2==0):
            self.drawLines()

        elif(self.numberOfSensors>1):
            for ls in self.locationOfSensors:
                try:
                    if(self.locationOfMotors.count(ls+1)):
                        self.pairs.append(([ls],[ls+1]))
                        self.drawIndLines(ls,ls)#only draw straight lines if there are more than one sensors
                except:
                    print("something weird")
                    pass

        light_matrix.show(self.temp)
        return self.temp

    def drawLines(self):
        #draws multi lines for singgle sensor condition]
        self.temp[(self.locationOfSensors[0])*5+0]=100
        self.temp[(self.locationOfSensors[0])*5+1]=100
        self.temp[(self.locationOfSensors[0])*5+2]=100
        self.pairs.append((self.locationOfSensors, self.locationOfMotors))
        for motorlocation in self.locationOfMotors:
            self.temp[(motorlocation-1)*5+2]=100
            self.temp[(motorlocation-1)*5+3]=100
            self.temp[(motorlocation-1)*5+4]=100

        #drawing the vertical lines
        minval=min(self.locationOfMotors+self.locationOfSensors)
        maxval=max(self.locationOfMotors+self.locationOfSensors)

        for i in range(minval,maxval):
            self.temp[i*5+2]=100

    def drawIndLines(self,sensor,motor): # draws individual lines for multi sensor condition
        self.temp[sensor*5+0]=100
        self.temp[sensor*5+1]=100
        self.temp[sensor*5+2]=100
        self.temp[motor*5+2]=100
        self.temp[motor*5+3]=100
        self.temp[motor*5+4]=100

        for i in range(sensor,motor): #drawing the vertical lines
            self.temp[i*5+2]=100
            #print("drew individual lines")

    def makepairs(self):
        return(self.pairs)


class SmartMotors:
    def __init__(self, sensors, motors):
        self.sensors=sensors
        self.motors=motors
        self.data=[]


    def drawImage(self, sens, mots):
        self.temp = [0] * 25
        self.temp[(sens[0])*5+0]=100
        self.temp[(sens[0])*5+1]=100
        self.temp[(sens[0])*5+2]=100
        for mot in mots:
            self.temp[(mot-1)*5+2]=100
            self.temp[(mot-1)*5+3]=100
            self.temp[(mot-1)*5+4]=100

        #drawing the vertical lines
        minval=min(sens+mots)
        maxval=max(sens+mots)

        for i in range(minval,maxval):
            self.temp[i*5+2]=100

        light_matrix.show(self.temp)
        return self.temp


    def train(self):
        while(buttonPressed(Run)<100):
            sensorValue=device.data(self.sensors[0])[0]
            motorValue=[]
            for motorPort in self.motors:
                self.drawImage(self.sensors, self.motors)
                motorValue.append(motor.relative_position(motorPort))
                if(buttonPressed(Data)>200):
                    playmusic(saveTone)
                    while(buttonPressed(Data)>0):
                        pass #wait till the left button is released
                    self.data.append([sensorValue,motorValue])
                    time.sleep(0.1)
        playmusic(trainTone)
        while(buttonPressed(Run)>10):
            pass
            #debounce






    def play(self):
        sensorValue=device.data(self.sensors[0])[0]
        min = 1000000
        pos = 0
        for (l, a) in self.data:
            dist = abs(sensorValue - l)
            if dist < min:
                min = dist
                pos = a

        for index, motorPort in enumerate(self.motors):
            motor.run_to_relative_position(motorPort,pos[index],9000)


    def showData(self):
        return(self.data)




def main():
    rgb.color(0,3) #set the blue to indicate start
    playmusic(startTone) #change this to mario
    s=Connections()
    snapShotofConnection=[0]*25
    while(buttonPressed(Run)<100):
        snapShotofConnection=s.ShowAllConnections()
        blink()

    #Now we are in train mode.
    playmusic(trainTone)
    rgb.color(0,8) # 8 color for Training Mode
    #wait till you leave the button
    while(buttonPressed(Run)>10):
        time.sleep(1)
        pass

    #record the sensors and motors plugged in
    pairs= s.makepairs()
    SM=[] 
    for index,pair in enumerate(pairs):
        try:
            sensorPort,motorPort=pair
            SM.append(SmartMotors(sensorPort,motorPort))
        except:
            pass
            #light_matrix error


    for smartmotor in SM:
        try:
            smartmotor.train()
        except:
            pass
        #dislay error

    playmusic(runTone)

    rgb.color(0,6) # GREEN color for Playing Mode
    while(buttonPressed(Data)<100):
        light_matrix.show(snapShotofConnection)
        for smartmotor in SM:
            smartmotor.play()
            time.sleep(0.1)

    while(buttonPressed(Data)>10):
        pass

while(not buttonPressed(Run)):
    main()
