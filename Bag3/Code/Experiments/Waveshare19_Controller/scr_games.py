# Screen 2: Games list. Tapping a game opens its tags (screen 3).
import tokens as t
import fake_data as fake
import ui


def build():
    s = ui.screen("games")
    ui.header(s, "Games")
    y = 80
    for i, (name, pulls) in enumerate(fake.GAMES[:3]):
        ui.row(s, y, name, str(pulls), selected=(i == 0), fn=lambda: ui.go("tags"))
        y += 52
    ui.row(s, y, "Utility tags", fn=lambda: ui.go("tags"))
    return s


ui.register("games", build)
