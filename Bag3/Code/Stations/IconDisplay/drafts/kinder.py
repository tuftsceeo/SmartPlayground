import runpy, sys
sys.argv = [sys.argv[0], "kinder"] + sys.argv[1:]
runpy.run_path(__file__.replace("kinder.py", "samples.py"), run_name="__main__")
