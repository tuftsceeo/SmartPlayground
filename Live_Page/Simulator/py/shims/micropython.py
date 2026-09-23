"""Fake `micropython` module — import safety only."""


def const(x):
    return x


def opt_level(level=None):
    if level is None:
        return 0
    return level


def mem_info(*a, **k):
    pass


def qstr_info(*a, **k):
    pass


def stack_use():
    return 0


def heap_lock():
    pass


def heap_unlock():
    pass


def kbd_intr(x):
    pass


def schedule(func, arg):
    try:
        func(arg)
    except Exception:
        pass
