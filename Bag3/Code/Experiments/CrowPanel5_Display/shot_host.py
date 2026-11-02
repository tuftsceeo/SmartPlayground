"""Host tool: run code on the panel's raw REPL and pull screenshots taken by shot.py.

    python3 shot_host.py exec "print(1)"
    python3 shot_host.py put shot.py
    python3 shot_host.py shot out.png
    python3 shot_host.py tap X Y [hold_ms] [out.png]

Opening the port leaves DTR/RTS low, so it does not reset the board. The first exec stops
the teacher tool's main loop; resume it with `exec "panel.run()"` (does not return).
"""

import binascii
import sys
import time

import serial
from PIL import Image

PORT = "/dev/cu.usbserial-310"
BAUD = 115200


def open_port():
    s = serial.Serial()
    s.port = PORT
    s.baudrate = BAUD
    s.timeout = 0.2
    s.dtr = False
    s.rts = False
    s.open()
    return s


def _read_until(s, end, timeout):
    buf = b""
    t0 = time.time()
    while not buf.endswith(end):
        b = s.read(4096)
        if b:
            buf += b
            t0 = time.time()
        elif time.time() - t0 > timeout:
            raise TimeoutError(f"waiting for {end!r}; got {buf[-200:]!r}")
    return buf


def raw_enter(s):
    s.write(b"\r\x03\x03")
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(b"\r\x01")
    _read_until(s, b"raw REPL; CTRL-B to exit\r\n>", 5)


def raw_exec(s, code, timeout=30):
    """Run code in raw REPL; returns stdout bytes, raises on a device exception."""
    s.write(code.encode() + b"\x04")
    buf = _read_until(s, b"\x04>", timeout)
    if not buf.startswith(b"OK"):
        raise RuntimeError(f"no OK: {buf[:200]!r}")
    out, err = buf[2:-2].split(b"\x04", 1)
    if err.strip():
        raise RuntimeError(err.decode(errors="replace"))
    return out


def raw_leave(s):
    s.write(b"\x02")
    time.sleep(0.1)


def run(code, timeout=60):
    s = open_port()
    try:
        raw_enter(s)
        out = raw_exec(s, code, timeout)
        raw_leave(s)
        return out
    finally:
        s.close()


def put(path, dest=None):
    dest = dest or path.rsplit("/", 1)[-1]
    data = open(path, "rb").read()
    s = open_port()
    try:
        raw_enter(s)
        raw_exec(s, f"f=open({dest!r},'wb')")
        for i in range(0, len(data), 512):
            raw_exec(s, f"f.write({data[i:i + 512]!r})")
        raw_exec(s, "f.close()")
        out = raw_exec(s, f"import os;print(os.stat({dest!r})[6])")
        raw_leave(s)
        return out
    finally:
        s.close()


def _unrle(data, px_bytes):
    out = bytearray()
    step = 1 + px_bytes
    for i in range(0, len(data) - step + 1, step):
        out += data[i + 1:i + step] * data[i]
    return bytes(out)


def decode(out):
    """Parse shot.py frames ('#F name w h bpp' then base64 lines, '#E') into PIL images."""
    imgs = {}
    cur = None
    for line in out.split(b"\n"):
        line = line.strip()
        if line.startswith(b"#F "):
            _, name, w, h, bpp = line.split()
            cur = [name.decode(), int(w), int(h), int(bpp), bytearray()]
        elif line == b"#E" and cur:
            name, w, h, bpp, rle = cur
            raw = _unrle(bytes(rle), bpp // 8)
            if bpp == 16:
                px = bytearray()
                for i in range(0, w * h * 2, 2):
                    v = raw[i] | (raw[i + 1] << 8)
                    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
                    px += bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
                imgs[name] = Image.frombytes("RGB", (w, h), bytes(px))
            else:
                # LVGL ARGB8888 is B, G, R, A in memory
                imgs[name] = Image.frombytes("RGBA", (w, h), raw[:w * h * 4], "raw", "BGRA")
            cur = None
        elif cur and line:
            cur[4] += binascii.a2b_base64(line)
    return imgs


def save(out, path):
    imgs = decode(out)
    img = imgs["screen"].convert("RGBA")
    if "top" in imgs:
        img = Image.alpha_composite(img, imgs["top"])
    img.convert("RGB").save(path)
    return path


def batch(steps, outdir="."):
    """steps: (png name or None, code). Code runs, then a grab when a name is given."""
    s = open_port()
    try:
        raw_enter(s)
        raw_exec(s, "import shot")
        for name, code in steps:
            out = raw_exec(s, code + ("\nshot.grab()" if name else ""), 180)
            if name:
                print(save(out, f"{outdir}/{name}.png"))
            keep, inframe = [], False
            for l in out.split(b"\n"):
                if l.startswith(b"#F "):
                    inframe = True
                elif l.startswith(b"#E"):
                    inframe = False
                elif not inframe and not l.startswith(b'{"mem"'):
                    keep.append(l)
            text = b"\n".join(keep).strip()
            if text:
                print(f"[{name or code[:40]}] " + text.decode(errors="replace"))
        raw_leave(s)
    finally:
        s.close()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "batch":
        ns = {}
        exec(open(sys.argv[2]).read(), ns)
        batch(ns["STEPS"], sys.argv[3])
        sys.exit()
    if cmd == "exec":
        sys.stdout.write(run(sys.argv[2], timeout=float(sys.argv[3]) if len(sys.argv) > 3 else 60).decode(errors="replace"))
    elif cmd == "put":
        for p in sys.argv[2:]:
            print(p, put(p).decode().strip())
    elif cmd == "shot":
        print(save(run("import shot;shot.grab()", 180), sys.argv[2]))
    elif cmd == "tap":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        hold = int(sys.argv[4]) if len(sys.argv) > 4 else 80
        code = f"import shot;shot.tap({x},{y},{hold})"
        if len(sys.argv) > 5:
            print(save(run(code + ";shot.grab()", 180), sys.argv[5]))
        else:
            sys.stdout.write(run(code).decode())
