import machine
import code_link

cause = machine.reset_cause()
code_link.prewarm()
mgr = code_link.NativeManager()
mgr.init()

import m0_stress
m0_stress.run(mgr, cause)
