import sys
from PIL import Image

W = 16
H = 16

def convert(path):
    img = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
    img = Image.alpha_composite(bg, img).convert("RGB").resize((W, H), Image.NEAREST)
    px = []
    for row in range(H):
        for col in range(W):
            px.append(img.getpixel((col, row)))
    return px

def preview(px):
    for row in range(H):
        line = ""
        for col in range(W):
            r, g, b = px[row * W + col]
            line += "\x1b[48;2;%d;%d;%dm  \x1b[0m" % (r, g, b)
        print(line)

def write(px, out):
    with open(out, "w") as f:
        f.write("ICON = (\n")
        for row in range(H):
            f.write("    " + ", ".join(str(p) for p in px[row*W:(row+1)*W]) + ",\n")
        f.write(")\n")

if __name__ == "__main__":
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "icon_out.py"
    px = convert(path)
    preview(px)
    write(px, out)
    print("wrote", out)
