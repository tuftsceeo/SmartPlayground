"""STEP 4: the real wand_main (libraries from /benchmpy), hard reset after RUN_MS."""
RUN_MS = 100000
import sys
sys.path.insert(0, "/benchmpy")
import machine
machine.Timer(0).init(mode=machine.Timer.ONE_SHOT, period=RUN_MS, callback=lambda t: machine.reset())
import wand_main
