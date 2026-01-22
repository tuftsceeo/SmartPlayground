config.py -- set of variables that can be sent on the json screen (color, sound, number, etc)

> **Note**: The following code from the Control Panel is currently not up to date with the latest Splat config variables. (For example, TrafficL no longer exists in config.py)
 ``` 
 # FROM CONTROL PANEL main.py
        if send_pressed:
            send_pressed = False
            print("Send button pressed")
            config = {
                "SetConfig": {
                    "sound": setSound(sound),
                    "light": setColor(color),
                    "pattern": pattern_choice,
                    "TrafficL": setPicture(picture) # this is currently for the light panel (pre traffic light)
                }
            }
            e.send(peer, str(config))
            print(str(config))
            await asyncio.sleep_ms(200)
```
> Check with Milan about config file operation.

The above code will need to match up with the following from main.py (Splat code):
```
 # FROM SPLAT COMPANION main.py
                if key == 'SetConfig':
                    s.buzz()
                    s.gotConfigFile()
                    print(receivedMessage)
                    msg = receivedMessage[key]
                    #s.color = s.bytearray_to_numbers(msg)
                    updateConfig(msg["sound"],msg["TrafficL"], msg["pattern"], msg["light"][0], msg["light"][1], msg["light"][2])
                    s.splat.sound = msg["sound"]
                    s.lred = msg["light"][0]
                    s.lgreen = msg["light"][1]
                    s.lblue = msg["light"][2]
                    s.lpattern = msg["pattern"]
                    s.Tcolor = msg["TrafficL"]
```

ble_splat.py is the splat control code.
main.py is the ble to esp-32 connection code. 

