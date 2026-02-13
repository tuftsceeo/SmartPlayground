from pyscript import document, window, WebSocket

import json
from time import sleep
import inspect, sys

def iscoroutinefunction(obj):
    """
    Cross-interpreter implementation of inspect.iscoroutinefunction.
    """
    is_micropython = "micropython" in sys.version.lower()
    if is_micropython:  # pragma: no cover
        # MicroPython seems to treat coroutines as generators :)
        # But the object may be a closure containing a generator.
        if "<closure <generator>" in repr(obj):
            # As far as I can tell, there's no way to check if a closure
            # contains a generator in MicroPython except by checking the
            # string representation.
            return True
        # And if not, just check it's a generator function.
        return inspect.isgeneratorfunction(obj)

    return inspect.iscoroutinefunction(obj)

class Channel():
    def __init__(self, channel, user, project):
        self.filter = None
        self.value = 0
        self.reply = ''
        self.callback = None
        self.color = 'green'

        self.url = ''
        self.socket = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2

        self.channel, self.user, self.project= channel, user, project
        self.topic = document.getElementById('topic')
        self.textbox = document.getElementById('channelValue')
        self.activity = document.getElementById('activity')
        self.liveBtn = document.getElementById('liveChan')
        self.to_send = document.getElementById('payload')
        self.send_it = document.getElementById('send')
        self.send_it.onclick = self.send_btn
        self.c_btn = document.getElementById('channel_connect')
        self.c_btn.onclick = self.connect_disconnect

    def connect_disconnect(self, event):   
        if self.c_btn.innerText == 'Connect':
            self.setupSocket()
            self.c_btn.innerText = 'Disconnect'
        else:
            self.c_btn.innerText = 'Connect'
            self.close()

    def setupSocket(self):
        self.url = f"wss://{self.user}.pyscriptapps.com/{self.project}/api/channels/{self.channel}"
        window.console.log(self.url)
        self.is_connected = False
        self._web_socket = None
        self.connect()
        
    async def onmessage(self, event):
        try:
            message = json.loads(event.data)
            #window.console.log('received ',message)
            await self.on_received(message)
        except:
            window.console.log('on receive error: ',message)
        
    async def on_received(self, message):
        if message['type'] == 'welcome':
            self.connected = True
            self.activity.innerText = json.dumps(message)
            self.liveBtn.style.backgroundColor = 'green'
        if message['type'] == 'data':
            if message['payload']:
                try:
                    topic, value = self.check(self.topic.value,message) 
                    self.reply = json.loads(message['payload'])
                    self.value = self.reply['value']
                    if value:
                        self.activity.innerText = message['payload']
                        self.textbox.innerText = self.value
                    if self.callback:
                        if iscoroutinefunction(self.callback):
                            print('awaiting')
                            await self.callback(message)
                        else:
                            self.callback(message)
                except Exception as e:
                    window.console.log('load error ',message)
                
    async def send(self,value):
        await self.post('', value)

    async def post(self, filter, value):
        if not self.is_connected:
            window.console.log('not connected')
            self.activity.innerText = 'Not connected - please connect to the channel first'
            return
        payload = {'topic':filter,'value':value}
        try:
            self.socket.send(json.dumps(payload))
        except Exception as e:
            window.console.log('post error ',e)
        self.color = 'lightgreen' if self.color == 'green' else 'green'
        self.liveBtn.style.backgroundColor = self.color    

    def connect(self):
        def onopen(event):
            self.activity.innerText = f"WebSocket connected: {now()}"
            self.is_connected = True
            self.reconnect_attempts = 0
        def onclose(event):
            self.liveBtn.style.backgroundColor = 'red'
            self.activity.innerText = f"WebSocket disconnected: {now()}"
            self.is_connected = False
            self.reconnect()
        self.socket = WebSocket(url=self.url, onopen=onopen, onclose=onclose, onmessage=self.onmessage)

    def reconnect(self):
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.activity.innerText = f"Attempting to reconnect ({self.reconnect_attempts}/{self.max_reconnect_attempts})"
            sleep(self.reconnect_delay)
            self.connect()

    def check(self, desired_topic, message):
        if (message['type'] == 'data' and 'payload' in message):
            topic, value = json.loads(message['payload'])['topic'], json.loads(message['payload'])['value']
            if (desired_topic == ""):
                return topic, value
            if topic.startswith(desired_topic):
                return topic, value
        return None, None
            
    async def send_btn(self, event):
        if not self.is_connected:
            return
        try:
            topic = self.topic.value
            value = self.to_send.value
            await self.post(topic,value)
        except Exception as e:
            print(e)
        
    def close(self):
        try:
            self.reconnect_attempts = self.max_reconnect_attempts
            self.is_connected = False
            self.liveBtn.style.backgroundColor = 'red'
            self.socket.close()
            self.activity.innerText = f"WebSocket disconnected: {now()}"
        except:
            pass
            
def now():
    import time

    # Get the current local time as a tuple.
    current_time_tuple = time.localtime()

    # Format the time as a string like `str(datetime.datetime.now())`.
    result = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        current_time_tuple[0],  # Year
        current_time_tuple[1],  # Month
        current_time_tuple[2],  # Day
        current_time_tuple[3],  # Hour
        current_time_tuple[4],  # Minute
        current_time_tuple[5],  # Second
    )

    return result
