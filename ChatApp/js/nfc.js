function generateWriteScript(text) {
    const escaped = text.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    return `
import machine, time, struct
from neopixel import NeoPixel

I2C_SDA=22; I2C_SCL=23; NEOPIXEL=20; SWITCH=0; BUZZER=19; PN532_ADDR=0x24; NUM_LEDS=25
TFI_H2P=0xD4; TFI_P2H=0xD5
CMD_GETFIRMWAREVERSION=0x02; CMD_SAMCONFIGURATION=0x14
CMD_INLISTPASSIVETARGET=0x4A; CMD_INDATAEXCHANGE=0x40
MIFARE_AUTH_A=0x60; MIFARE_AUTH_B=0x61; MIFARE_READ=0x30; MIFARE_WRITE=0xA0; NTAG_WRITE=0xA2
TAG_TYPES={(0x0044,0x00):"NTAG",(0x0004,0x00):"NTAG",(0x0004,0x08):"MIFARE Classic",(0x0002,0x08):"MIFARE Classic",(0x0004,0x20):"MIFARE Plus"}
COMMON_KEYS=[b'\\xFF\\xFF\\xFF\\xFF\\xFF\\xFF',b'\\xD3\\xF7\\xD3\\xF7\\xD3\\xF7',b'\\xA0\\xA1\\xA2\\xA3\\xA4\\xA5',b'\\x00\\x00\\x00\\x00\\x00\\x00']

TEXT = '${escaped}'

class LEDAnimator:
    def __init__(self,pin,n):
        self.np=NeoPixel(machine.Pin(pin),n); self.n=n
    def clear(self):
        [self.np.__setitem__(i,(0,0,0)) for i in range(self.n)]; self.np.write()
    def fill(self,c):
        [self.np.__setitem__(i,c) for i in range(self.n)]; self.np.write()
    def waiting_for_tag(self,frame):
        self.clear()
        pos=frame%self.n
        for i in range(3):
            idx=(pos+i)%self.n; fade=max(0,30-i*10)
            self.np[idx]=(fade,fade//2,0)
        self.np.write()
    def writing_progress(self,progress):
        lit=int(progress*self.n)
        for i in range(self.n):
            self.np[i]=(0,0,40) if i<lit else ((40,40,40) if i==lit else (5,5,5))
        self.np.write()
    def success(self):
        for _ in range(3):
            self.fill((0,40,0)); time.sleep_ms(100); self.clear(); time.sleep_ms(100)
        for i in range(self.n):
            self.np[i]=(0,30,0); self.np.write(); time.sleep_ms(30)
        time.sleep(0.5)
        for b in range(30,-1,-2):
            self.fill((0,b,0)); time.sleep_ms(30)
        self.clear()
    def failure(self):
        for _ in range(5):
            self.fill((40,0,0)); time.sleep_ms(80); self.clear(); time.sleep_ms(80)

class Beeper:
    def __init__(self,pin): self.pin=pin
    def tone(self,freq,ms):
        buz=machine.PWM(machine.Pin(self.pin)); buz.freq(freq); buz.duty_u16(16384)
        time.sleep_ms(ms); buz.duty_u16(0); buz.deinit()
    def success(self):
        self.tone(523,100); time.sleep_ms(50); self.tone(659,100); time.sleep_ms(50); self.tone(784,200)
    def fail(self): self.tone(300,200); time.sleep_ms(50); self.tone(200,400)
    def click(self): self.tone(1000,30)

class PN532:
    def __init__(self,i2c,addr=0x24): self.i2c=i2c; self.addr=addr
    def _wait_ready(self,timeout=1000):
        start=time.ticks_ms()
        while True:
            try:
                if self.i2c.readfrom(self.addr,1)[0]==0x01: return True
            except OSError: pass
            if time.ticks_diff(time.ticks_ms(),start)>timeout: return False
            time.sleep_ms(10)
    def _write_cmd(self,cmd,params=b''):
        payload=bytes([TFI_H2P,cmd])+bytes(params); ln=len(payload)
        frame=bytearray([0x00,0x00,0xFF,ln,(~ln+1)&0xFF])+bytearray(payload)
        frame.append((~sum(payload)+1)&0xFF); frame.append(0x00)
        self.i2c.writeto(self.addr,frame)
    def _read_ack(self,timeout=500):
        if not self._wait_ready(timeout): raise RuntimeError("ACK timeout")
        self.i2c.readfrom(self.addr,7)
    def _read_resp(self,timeout=1000):
        if not self._wait_ready(timeout): raise RuntimeError("Response timeout")
        buf=bytes(self.i2c.readfrom(self.addr,64))
        for i in range(len(buf)-5):
            if buf[i]==0x00 and buf[i+1]==0xFF and i+4+buf[i+2]<=len(buf):
                flen=buf[i+2]
                if ((flen+buf[i+3])&0xFF)==0 and flen>0:
                    return buf[i+4:i+4+flen]
        raise RuntimeError("No valid frame")
    def cmd(self,cmd,params=b'',timeout=1000):
        self._write_cmd(cmd,params); time.sleep_ms(5); self._read_ack(timeout)
        resp=self._read_resp(timeout)
        if len(resp)<2 or resp[0]!=TFI_P2H or resp[1]!=(cmd+1): raise RuntimeError("Bad resp")
        return resp[2:]
    def init(self):
        fw=self.cmd(CMD_GETFIRMWAREVERSION); print("PN532 fw: %d.%d" % (fw[1],fw[2]))
        self.cmd(CMD_SAMCONFIGURATION,b'\\x01\\x00\\x00')
    def detect_tag(self,timeout=500):
        try: r=self.cmd(CMD_INLISTPASSIVETARGET,b'\\x01\\x00',timeout)
        except RuntimeError: return None
        if len(r)<6 or r[0]==0: return None
        atqa=(r[2]<<8)|r[3]; sak=r[4]; uid_len=r[5]; uid=r[6:6+uid_len]
        return {'uid':uid,'uid_hex':':'.join(['%02X'%b for b in uid]),'atqa':atqa,'sak':sak,
                'tag_type':TAG_TYPES.get((atqa,sak),"Unknown"),
                'is_classic':sak in (0x08,0x18),'is_ntag':sak in (0x00,0x20)}
    def mifare_auth(self,uid,block,key=b'\\xFF\\xFF\\xFF\\xFF\\xFF\\xFF',kt=0x60):
        params=bytes([0x01,kt,block])+bytes(key)+bytes(uid[:4])
        try: r=self.cmd(CMD_INDATAEXCHANGE,params,1000); return (r[0]&0x3F)==0
        except RuntimeError: return False
    def mifare_write(self,block,data):
        if len(data)!=16: raise ValueError("Need 16 bytes")
        r=self.cmd(CMD_INDATAEXCHANGE,bytes([0x01,MIFARE_WRITE,block])+bytes(data),1000)
        if (r[0]&0x3F)!=0: raise RuntimeError("Write err")
    def ntag_write_page(self,page,data):
        if len(data)!=4: raise ValueError("Need 4 bytes")
        r=self.cmd(CMD_INDATAEXCHANGE,bytes([0x01,NTAG_WRITE,page])+bytes(data),1000)
        if (r[0]&0x3F)!=0: raise RuntimeError("Write err")

def build_ndef(text):
    lang=b'en'; payload=bytes([len(lang)])+lang+text.encode('utf-8')
    record=bytes([0xD1,1,len(payload)])+b'T'+payload
    return bytes([0x03,len(record)])+record+bytes([0xFE])

def write_ntag(nfc,tag,text,led):
    ndef=build_ndef(text)
    while len(ndef)%4!=0: ndef+=b'\\x00'
    pages=(len(ndef)+3)//4
    for i in range(pages):
        led.writing_progress((i+1)/pages)
        nfc.ntag_write_page(4+i,ndef[i*4:i*4+4])
        time.sleep_ms(30)
    return True

def write_mifare(nfc,tag,text,led):
    ndef=build_ndef(text)
    while len(ndef)%16!=0: ndef+=b'\\x00'
    blocks=len(ndef)//16
    writable=[]
    for sec in range(1,16):
        for b in range(3): writable.append(sec*4+b)
    for i in range(min(blocks,len(writable))):
        block=writable[i]; sector=block//4
        led.writing_progress((i+1)/blocks)
        resel=nfc.detect_tag(timeout=300)
        if not resel: return False
        authed=False
        for key in COMMON_KEYS:
            for kt in [MIFARE_AUTH_A,MIFARE_AUTH_B]:
                if nfc.mifare_auth(tag['uid'],sector*4,key,kt): authed=True; break
            if authed: break
        if not authed: return False
        nfc.mifare_write(block,ndef[i*16:i*16+16]); time.sleep_ms(30)
    return True

def write_once():
    print("Writing NFC card: " + TEXT)
    i2c=machine.SoftI2C(sda=machine.Pin(I2C_SDA),scl=machine.Pin(I2C_SCL),freq=100_000)
    btn=machine.Pin(SWITCH,machine.Pin.IN,machine.Pin.PULL_UP)
    led=LEDAnimator(NEOPIXEL,NUM_LEDS); beep=Beeper(BUZZER); led.clear()
    nfc=PN532(i2c,PN532_ADDR); nfc.init()
    print("Place tag on reader and press BUTTON to write...")
    frame=0; tag=None; tag_on=False
    while True:
        led.waiting_for_tag(frame); frame+=1
        detected=nfc.detect_tag(timeout=100)
        if detected and not tag_on:
            tag=detected; tag_on=True
            print("Tag ready: " + tag['uid_hex'] + " — press BUTTON!")
            beep.click(); led.fill((0,20,0))
        elif not detected and tag_on:
            tag_on=False; tag=None; print("Tag removed...")
        if btn.value()==0 and tag_on and tag:
            time.sleep_ms(50)
            if btn.value()==0: beep.click(); break
        time.sleep_ms(50)
    ok=False
    try:
        if tag['is_ntag']: ok=write_ntag(nfc,tag,TEXT,led)
        elif tag['is_classic']: ok=write_mifare(nfc,tag,TEXT,led)
        else: print("Unsupported tag: " + tag['tag_type'])
    except Exception as e: print("Error: " + str(e))
    if ok:
        print("Written: " + TEXT); led.success(); beep.success()
    else:
        print("Write failed!"); led.failure(); beep.fail()
    led.clear()

write_once()
`.trim();
}

export async function writeNfcTag(uboard, addMsg, text) {
    if (!uboard.connected) {
        addMsg("Connect your board first.", "system");
        return;
    }
    if (!text) {
        addMsg("No card text specified.", "system");
        return;
    }
    addMsg('Writing NFC card: "' + text + '" — place tag on wand and press the button.', "system");
    try {
        const script = generateWriteScript(text);
        await uboard.board.write("\x03");
        await sleep(300);
        await uboard.paste(script);
        uboard.focus();
    } catch (e) {
        addMsg("Error starting NFC writer: " + e, "system");
    }
}

export function showUploadModal() {
    return new Promise((resolve) => {
        const overlay = document.getElementById("upload-overlay");
        overlay.classList.remove("hidden");

        function onConfirm() {
            cleanup();
            const slot = parseInt(document.getElementById("upload-slot").value);
            overlay.classList.add("hidden");
            resolve({ confirmed: true, slot });
        }
        function onCancel() {
            cleanup();
            overlay.classList.add("hidden");
            resolve({ confirmed: false, slot: null });
        }
        function cleanup() {
            document.getElementById("btn-upload-confirm").removeEventListener("click", onConfirm);
            document.getElementById("btn-upload-cancel").removeEventListener("click", onCancel);
        }

        document.getElementById("btn-upload-confirm").addEventListener("click", onConfirm);
        document.getElementById("btn-upload-cancel").addEventListener("click", onCancel);
    });
}

// Shows all cards to write (trigger + game cards) before uploading.
// Returns a promise that resolves when the user clicks Skip or Done.
export function showBundledCardsModal(triggerText, gameCards, uboard, addMsg) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("nfc-bundle-overlay");
        const list = document.getElementById("nfc-bundle-list");
        list.innerHTML = "";

        // Build rows: trigger card first, then game cards
        const allCards = [{ text: triggerText, label: `Trigger — "${triggerText}"` }, ...gameCards.map((c) => ({ text: c, label: `Game card — "${c}"` }))];

        allCards.forEach(({ text, label }) => {
            const row = document.createElement("div");
            row.className = "nfc-card-item";
            row.innerHTML =
                `<span class="nfc-card-label">${label}</span>` +
                `<button class="btn nfc-btn" data-card="${text}">Write Tag</button>` +
                `<span class="nfc-card-status"></span>`;
            list.appendChild(row);
        });

        overlay.classList.remove("hidden");

        list.querySelectorAll("[data-card]").forEach((btn) => {
            btn.addEventListener("click", async () => {
                btn.disabled = true;
                btn.nextElementSibling.textContent = "Writing...";
                await writeNfcTag(uboard, addMsg, btn.dataset.card);
                btn.nextElementSibling.textContent = "✓ Done";
            });
        });

        function onDone() {
            cleanup();
            overlay.classList.add("hidden");
            resolve();
        }
        function onSkip() {
            cleanup();
            overlay.classList.add("hidden");
            resolve();
        }
        function cleanup() {
            document.getElementById("btn-nfc-bundle-done").removeEventListener("click", onDone);
            document.getElementById("btn-nfc-bundle-skip").removeEventListener("click", onSkip);
        }

        document.getElementById("btn-nfc-bundle-done").addEventListener("click", onDone);
        document.getElementById("btn-nfc-bundle-skip").addEventListener("click", onSkip);
    });
}

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}
