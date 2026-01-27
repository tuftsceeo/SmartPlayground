from games.sound import Notes
from games.shake import Shake
from games.jump import Jump
from games.hotcold import Hot_cold
from games.clap import Clap
from games.rainbow import Rainbow
from games.hibernate import Hibernate
from games.pattern_rainbow_btn import Pattern_btn
from games.pattern_rainbow_plushie import Pattern_plush
from games.color_press import Color_Press
from games.color_press_mult import Color_Press_Mult
from utilities.colors import *

class Config:
    name = "button"
    hw_version = 3
    sw_version = 3.2
    module_type = "button"
    first_game = 0
    color = PURPLE
    num_of_leds = 12
    intensity = 0.1
    volume = 1.0
    antenna = True
    games = [(Notes,0.1), (Shake,0.1), (Hot_cold,0.1), (Jump,0.1),
             (Clap,0.1), (Rainbow,0.1), (Hibernate,0.1),
             (Pattern_btn,0.1), (Pattern_plush,0.5),
             (Color_Press, 0.1), (Color_Press_Mult, 0.1)]
    
class Plushie_settings(Config):
    module_type = "plushie"
    num_of_leds = 12

class Box_settings(Config):
    module_type = "box"
    hw_version = 2
    num_of_leds = 25
    
class Splats_settings(Config):
    module_type = "splats"
    num_of_leds = 3
    
class Button_settings(Config):
    module_type = "button"
    first_game = 7

class Controller_settings(Config):
    module_type = "controller"
    num_of_leds = 0
    first_game = 0

#hw_version:
# sophies version : 1
# 2nd version     : 2
# box verson      : 3

#sw_version :
#sophies version : 1
#october_version : 2
#current _version : 3

