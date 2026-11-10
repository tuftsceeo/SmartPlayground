import runpy, sys
sys.argv = [sys.argv[0], "playground"] + sys.argv[1:]
runpy.run_path(__file__.replace("playground.py", "samples.py"), run_name="__main__")
