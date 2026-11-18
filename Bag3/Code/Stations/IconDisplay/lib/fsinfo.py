"""fsinfo.py -- one free-space line for the boot log.

Its own module, imported by main._boot() after the radio is up (AGENTS.md:
nothing may allocate before the radio claims its memory).
"""
import os


def report(path="/"):
    try:
        s = os.statvfs(path)
        bsize = s[0]
        total = s[2] * bsize
        free = s[3] * bsize
        print(f"  Flash free: {free // 1024} KB of {total // 1024} KB")
    except Exception as e:
        print(f"  Flash free: unknown ({e})")
