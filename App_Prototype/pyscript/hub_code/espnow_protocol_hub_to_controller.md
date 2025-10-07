RSSI Values:
-20 Here
-40 Close
-?  Distant
-?  Far
-90 All

These are example messages sent by the physical button hub that is being replaced by the web app. The RSSI value can be anything between -20 and -90 to specify the module range.  These are all the commands currently implemented on the modules - leave all other commands as placehold print statements. 

"""
message  = {"batteryCheck": {"RSSI": -40, "value": 0}} # request Close (-40)modules to show battery on the module screen (no values returned)

message = {"rainbow": {"RSSI": -40, "value": 0}} # send rainbow/winning animation command to Close modules (no values returned)

message = {"lightOff": {"RSSI": -90, "value": 0}} # send Pause command to All modules (no values returned)
    
message = {"deepSleep": {"RSSI": -90, "value": 0}} # send Off command to All modules (no values returned)

message = {"updateThreshold": {"RSSI": -40, "value": THRESHOLD}} # send Update Threshold command to Close modules (no command on modules yet) this sends the THRESHOLD variable value to close modules

message = {"updateGame": {"RSSI": -40, "value": self.encoder_value}} # send Update Game command to Close modules this sends the [self.encoder_value] (0 to 9) variable value to close modules each number representing a game.

"""