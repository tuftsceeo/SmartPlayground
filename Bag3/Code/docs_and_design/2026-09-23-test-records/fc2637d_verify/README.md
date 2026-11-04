# fc2637d flash-and-verify: heap guard + timeout pairing

Reflashed both Dials + wand to `fc2637d` (per the sparring partner's
FLASH-AND-VERIFY request), verified every file by read-back diff, hard-reset
both Dials with `DEBUG_SERVE=True` / `DEBUG_PULL=True` kept on.

**Gate 1 (arm):** both Dials armed clean, well above the 22000 floor --
Dial 1 `idf_free=29216`, Dial 2 `idf_free=29228` (both `idf_largest=20480`).
No guard reboot needed on either.

**Gate 2 (20 scripted wand pulls against Dial 1, Dial 2 also armed):
20/20 OK.** `cycle_1.txt`-`cycle_20.txt`, each `pull OK` in 12.7-18.3s. Zero
F1/F2/F3 failures -- a complete turnaround from the pre-fix T2 run (10/10
fail) and T5 (4/4 fail) documented in
`../2026-09-23-debug-handoff-multihost-pull.md`.

**Gate 3 (2 min idle, no pulls):** PASS. `dial1_continuous.txt` shows
`idf_free` flat at 28796 (above the 22000 floor) for the full window, no
guard reboot, `up=` counter climbing uninterrupted the whole time.

Net: the `5781335`/`fc2637d` fix (shorter reply timeout, single attempt,
heap-guard reboot) appears to fully resolve the failure mode T2/T4/T5
characterized earlier. Not yet re-tested against Dial 2 as the pull target
(this run used Dial 1), nor under the higher-load T5-style two-Dial-active
condition -- worth a follow-up run before calling this fully closed.
