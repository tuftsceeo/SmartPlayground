"""Stub: bench instrumentation, a no-op for wire tests."""
def probe(*a, **k): pass
def mark(*a, **k): return (0, 0)
def span(*a, **k): pass
def frag(*a, **k): pass
