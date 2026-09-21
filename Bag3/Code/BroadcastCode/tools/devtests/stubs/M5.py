"""Bare M5Stack UIFlow2 stub, just enough for a Box/Dial firmware module to
import under CPython. Nothing here is called by the host devtests -- they
only exercise _boot_scan_games(), which never touches the screen or buttons.
"""


class _Btn:
    def isPressed(self):
        return False

    def wasPressed(self):
        return False


BtnA = _Btn()
BtnB = _Btn()


class Speaker:
    @staticmethod
    def setVolume(v):
        pass

    @staticmethod
    def tone(freq, ms):
        pass


class _Fonts:
    Montserrat12 = None
    Montserrat16 = None
    Montserrat18 = None


class _Rectangle:
    def __init__(self, *a, **k):
        pass


class _Label:
    def __init__(self, *a, **k):
        pass


class _Triangle:
    def __init__(self, *a, **k):
        pass


class Widgets:
    FONTS = _Fonts
    Rectangle = _Rectangle
    Label = _Label
    Triangle = _Triangle

    @staticmethod
    def setRotation(n):
        pass

    @staticmethod
    def fillScreen(color):
        pass


def begin():
    pass


def update():
    pass
