"""
Fake `_thread` — schedules callables as asyncio tasks.
"""

import asyncio


def start_new_thread(fn, args=(), kwargs=None):
    kwargs = kwargs or {}

    async def _runner():
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            await result

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_runner())
    except RuntimeError:
        # No running loop — just call sync
        fn(*args, **(kwargs or {}))


def get_ident():
    return 1


def stack_size(size=None):
    return 0


allocate_lock = None


class Lock:
    def acquire(self, *a, **k):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def allocate_lock():
    return Lock()
