def on_on_start():
    basic.show_icon(IconNames.HOUSE)
ml.on_start(ml.event.nothing, on_on_start)

def on_button_pressed_a():
    bluetooth.uart_write_string("A")
input.on_button_pressed(Button.A, on_button_pressed_a)

def on_on_start2():
    basic.show_icon(IconNames.DUCK)
    bluetooth.uart_write_string("shake")
ml.on_start(ml.event.shake, on_on_start2)

def on_button_pressed_b():
    bluetooth.uart_write_string("B")
input.on_button_pressed(Button.B, on_button_pressed_b)

def on_on_start3():
    basic.show_icon(IconNames.TORTOISE)
    bluetooth.uart_write_string("point")
ml.on_start(ml.event.point, on_on_start3)

def on_on_start4():
    basic.show_icon(IconNames.STICK_FIGURE)
    bluetooth.uart_write_string("round")
ml.on_start(ml.event.rount, on_on_start4)

bluetooth.start_uart_service()