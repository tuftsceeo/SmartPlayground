from pyscript import document, window, when
import splats
import channel
import asyncio

COLORS = [
    (255, 0, 0),
    (255, 165, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 0, 255),
    (75, 0, 130),
    (238, 130, 238),
    (255, 255, 255),
]

SOUNDS = [
    19, # cat
    20, # chicken
    21, # cow
    22, # dog
    23, # pig
    24, # duck
    25, # elephant
    26, # horse
]

myHub = splats.Hub()
myChannel = channel.Channel("hackathon", "@chrisrogers", "talking-on-a-channel")
myChannel.connect_disconnect(None)
chan_topic = document.getElementById('topic')

c_btn = document.getElementById('ble')
liveBtn = document.getElementById('live')
waitfor = document.getElementById('waitfor')
light = document.getElementById('do_light')
sound = document.getElementById('do_sound')
note = document.getElementById('do_note')

@when("click", "#ble")
async def ask(event):
    if c_btn.innerText == 'Connect Device':
        await myHub.connect('Splat')
        window.console.log('connected')
        c_btn.innerText = 'Disconnect'
        liveBtn.style.backgroundColor = 'green'
    else:
        myHub.disconnect()
        window.console.log('disconnected')
        c_btn.innerText = 'Connect Device'
        liveBtn.style.backgroundColor = 'red'
    
@when("click", "#test")
async def test(event):
    #await myHub.myble.write([0x00, 0x20, 0x02, 0xFF])
    await myHub.write([0x00, 0x20, 0x02, 0xFF])
    window.console.log('testing')

async def theCall(message):
    topic, value = myChannel.check(chan_topic.value,message)
    if topic and value:
        if waitfor.value == 'chan':
            await theAction()

async def theEvent(data):
    if data[0] == 3: # btn
        if data[2] ==0: # released
            window.console.log(f'released: {waitfor.value}')
            myChannel.post(chan_topic.value + '/release',waitfor.value)
            if waitfor.value == 'release':
                await theAction()
        else:
            window.console.log(f'pressed: {waitfor.value}')
            myChannel.post(chan_topic.value + '/press',waitfor.value)
            if waitfor.value == 'press':
                await theAction()

async def theAction():
    window.console.log(f'Action {light.value}, {sound.value}')
    if light.value == 'nix':
        pass
    else:
        await myHub.setLEDsON(list(COLORS[int(light.value)]))
        window.console.log('color: ', light.value)
    if sound.value == 'nada':
        pass
    elif sound.value == 'note':
        await myHub.noteOn(int(note.value), 255, 4, 16)
        window.console.log('note ', note.value) 
        await asyncio.sleep(0.5)
        await myHub.noteOff(int(note.value), 255, 4, 16)
    else:
        await myHub.playSound(SOUNDS[int(sound.value)], 255)
        window.console.log('sound ', sound.value)

myHub.callback = theEvent
myChannel.callback = theCall