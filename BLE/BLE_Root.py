from BLE_CEEO import Listen
import time, struct

class Root():
    def __init__(self):
        self.ID = 0
    
    def crc8(parse, data):
        crc = 0
        data = data[0:19]
        for c in data:
            for i in range(7,-1,-1):
                bit = crc & 0x80
                bit = 1 if bit>0 else 0
                if c & 2**i:
                    bit = not bit
                crc <<= 1
                if bit:
                    crc ^= 0x07   
            crc &= 0xff
        return crc & 0xff
    
    def parse(self, data):
        self.function = {(0,0):self.version, (0,2):self.name,(0,4):self.stop_project,(0,14):self.serial_number,(1,8):self.distance_done, (1,12):self.arc_done, (4,2):self.color_sensor,(12,0):self.bump_sensor,(13,0):self.light_sensor,(17,0):self.touch_sensor}
        dev = data[0]
        cmd = data[1]
        ID = data[2]
        payload = data[3:19]
        self.crc = data[19]
        if not self.crc == self.crc8(data[0:19]+b'\x00'):
            print('crc error: ',end='')
            print(data)
            return None
        
        key = (dev,cmd)
        return self.function[key](payload) if key in self.function else self.default(dev,cmd,ID,payload)

    def version(self, payload):
        data=list(payload)
        print('Version: FW = %d.%d, HW = %d.%d, Boot = %d.%d, Protocol = %d.%d, Patch = %d' %(data[0],data[1],data[2],data[3],data[4],data[5],data[6],data[7],data[8]))

    def name(self, payload):
        print('Name: ' + str(payload.decode().split('\x00')[0]))

    def stop_project(self, payload):
        print('Stop Event: ' )

    def serial_number(self, payload):
        print('Serial Number: ' + str(payload.decode()[0:12]))

    def color_sensor(self, payload):
        light = []
        for p in payload:
            light.append(p>>4)
            light.append(p&0b1111)
        return light

    def bump_sensor(self, payload):
        LUT = {0x00: 'No',0x40:'Right', 0x80:'Left', 0xC0:'Both'}
        time = struct.unpack('>I',payload[:4])[0]/1000
        state = struct.unpack('B',payload[4:5])[0]
        if state in LUT: state = LUT[state]
        print(time, state)
        
    def light_sensor(self, payload):
        LUT = {4: 'both dark', 5:'Right', 6:'Left', 7:'both bright'}
        time = struct.unpack('>I',payload[:4])[0]/1000
        state = struct.unpack('B',payload[4:5])[0]
        left = struct.unpack('H',payload[5:7])[0]
        right = struct.unpack('H',payload[7:9])[0]
        if state in LUT: state = LUT[state]
        print(time, state, left, right)
        
    def distance_done(self, payload):
        [time, X, Y] = struct.unpack('>III',payload[:12])
        print('Done moving the distance: %0.2f (%d,%d) mm'%(time/1000,X,Y))
    
    def arc_done(self, payload):
        [time, X, Y, heading] = struct.unpack('>IIIh',payload[:14])
        print('Done moving the arc: %0.2f (%d,%d) mm heading %d'%(time/1000,X,Y,heading))
    
    def touch_sensor(self, payload):
        LUT = {0b1000: 'front-left', 0b100:'front-right', 0b10:'rear-right', 0b1:'rear-left'}
        time = struct.unpack('>I',payload[:4])[0]/1000
        state = struct.unpack('B',payload[4:5])[0] >> 4
        states = ''
        for l in LUT:
            if l & state : states += LUT[l] + ' '
        print('Touch: %f  %s' % (time, states))

    def battery_drop(self, payload):
        time = struct.unpack('>I',payload[:4])[0]/1000
        [voltage, percent] = struct.unpack('HB',payload[4:7])
        print('Your battery level dropped: voltage %.2f  or %d percent'%(voltage/1000,percent))
    
        
    def default(self, dev,cmd,ID,payload):
        print(dev,cmd,ID,payload)

# -----------------------


    def wrap(self, dev, cmd, payload = [0]*16, ID = None):
        if not ID:
            ID = self.ID
        payload = payload[0:16]
        self.wrapped = [0x00]*20
        self.wrapped[0:3] = [dev,cmd,ID]
        self.wrapped[3:3+len(payload)] = list(payload)
        self.wrapped[19] = self.crc8(bytearray(self.wrapped[0:19]))
        self.ID += 1
        #print(self.wrapped)
        return bytearray(self.wrapped)
    
    def coerce(self, value, low = -100, high = 100):
        return max(min(value, high),low)

    def motors(self, left_speed = 100, right_speed = 100):  #-100 to 100 in mm/s
        payload = struct.pack('>ii',self.coerce(left_speed),self.coerce(right_speed))#+bytearray([0]*8)
        return self.wrap(1,4,payload)

    def motor(self, speed = 100, left = True):  #-100 to 100 in mm/s
        payload = struct.pack('>i',self.coerce(speed))#+bytearray([0]*8)
        cmd = 6 if left else 7
        return self.wrap(1,cmd,payload)

    def distance(self, dist = 10):  # distance in mm
        payload = struct.pack('>i',self.coerce(dist, -2147483648, 2147483647))
        return self.wrap(1,8,payload)

    def angle(self, angle = 10):  # distance in mm
        payload = struct.pack('>i',self.coerce(angle, -2147483648, 2147483647))
        return self.wrap(1,12,payload)

    def gravity(self, active = 1, amount = 50.0):  # active: 0 off, 1 on, 2 enabled when marker down
        amount = int(amount*10)
        payload = struct.pack('>BI',self.coerce(active, 0, 2),self.coerce(amount, 0, 1000))
        return self.wrap(1,8,payload)

    def get_versions(self, board = 0xA5):  #0xA5 = main, 0xC6 = color
        payload = struct.pack('B',board)#+bytearray([0]*15)
        return self.wrap(0,0,payload)

    def set_name(self, name = 'fred'):
        name = name[0:16].encode()
        return self.wrap(0,1, name)
    
    def get_name(self):
        return self.wrap(0,2)
    
    def stop(self):
        return self.wrap(0,3)

    def disconnect(self):
        return self.wrap(0,6)
    
root = Root()

def central(name):   
    try:   
        L = Listen(name, verbose = True)
        if L.connect_up():
            print('L connected')
            L.send(root.get_versions())
            while L.is_connected:
                time.sleep(4)
                if L.is_any:
                    reply = root.parse(L.read())

    except Exception as e:
        print(e)
    finally:
        L.disconnect()
        print('closing up')

central('CRoot')
