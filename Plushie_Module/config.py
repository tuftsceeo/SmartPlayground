from games.sound import Notes
from games.shake import Shake
from games.jump import Jump
from games.hotcold import Hot_cold
from games.clap import Clap
from games.rainbow import Rainbow
from games.hibernate import Hibernate
from games.pattern_rainbow_btn import Pattern_btn
from games.pattern_rainbow_plushie import Pattern_plush
from utilities.colors import *

class Config:
    name = "button"
    hw_version = 2.0
    sw_version = 3.2
    module_type = "button"
    first_game = 0
    default_color = PURPLE
    default_intensity = 0.1
    default_volume = 1.0
    antenna = True
    games = [(Notes,0.1), (Shake,0.1), (Hot_cold,0.1), (Jump,0.1),
             (Clap,0.1), (Rainbow,0.1), (Hibernate,0.1),
             (Pattern_btn,0.1), (Pattern_plush,0.5)]
    
class Plushie_settings(Config):
    module_type = "plushie"
    
class Splats_settings(Config):
    module_type = "splats"
    
class Button_settings(Config):
    module_type = "button"
    first_game = 7
    

#hw_version:
#sophies version : 1
#current version : 2

#sw_version :
#sophies version : 1
#october_version : 2
#current _version : 3
