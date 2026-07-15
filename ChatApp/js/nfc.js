// ── MicroPython script generator ─────────────────────────────────────────────
// Protocol messages printed by the wand:
//   [NFC_FOUND:uid:tagtype]  — card on reader, webapp should confirm
//   [CARD_REMOVED]           — card left before confirmation
//   [WRITE_PROGRESS:n:total] — page/block written
//   [WRITE_DONE]             — success
//   [WRITE_FAILED:reason]    — error
//   [WRITE_CANCELLED]        — user sent 'n'
// Webapp sends back: 'y\n' (proceed) or 'n\n' (cancel)

function generateWriteScript(text) {
    const escaped = text.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return `
import machine, time, sys
from neopixel import NeoPixel
try:
    import select as _sel
    def _stdin_char():
        r,_,_=_sel.select([sys.stdin],[],[],0)
        return sys.stdin.read(1) if r else None
except ImportError:
    def _stdin_char(): return None

I2C_SDA=22; I2C_SCL=23; NEOPIXEL=20; BUZZER=19; PN532_ADDR=0x24; NUM_LEDS=25
TFI_H2P=0xD4; TFI_P2H=0xD5
CMD_GETFIRMWAREVERSION=0x02; CMD_SAMCONFIGURATION=0x14
CMD_INLISTPASSIVETARGET=0x4A; CMD_INDATAEXCHANGE=0x40
MIFARE_AUTH_A=0x60; MIFARE_AUTH_B=0x61; MIFARE_WRITE=0xA0; NTAG_WRITE=0xA2
TAG_TYPES={(0x0044,0x00):"NTAG",(0x0004,0x00):"NTAG",(0x0004,0x08):"MIFARE Classic",(0x0002,0x08):"MIFARE Classic",(0x0004,0x20):"MIFARE Plus"}
COMMON_KEYS=[b'\\xFF\\xFF\\xFF\\xFF\\xFF\\xFF',b'\\xD3\\xF7\\xD3\\xF7\\xD3\\xF7',b'\\xA0\\xA1\\xA2\\xA3\\xA4\\xA5',b'\\x00\\x00\\x00\\x00\\x00\\x00']
TEXT='${escaped}'

class LEDAnimator:
    def __init__(self,pin,n):
        self.np=NeoPixel(machine.Pin(pin),n); self.n=n
    def clear(self):
        for i in range(self.n): self.np[i]=(0,0,0)
        self.np.write()
    def fill(self,c):
        for i in range(self.n): self.np[i]=c
        self.np.write()
    def waiting(self,frame):
        self.clear()
        pos=frame%self.n
        for i in range(3):
            idx=(pos+i)%self.n; fade=max(0,30-i*10)
            self.np[idx]=(fade,fade//2,0)
        self.np.write()
    def progress(self,n,total):
        lit=int((n/total)*self.n)
        for i in range(self.n):
            self.np[i]=(0,0,40) if i<lit else ((40,40,40) if i==lit else (5,5,5))
        self.np.write()
    def success(self):
        for _ in range(3):
            self.fill((0,40,0)); time.sleep_ms(100); self.clear(); time.sleep_ms(100)
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
        fw=self.cmd(CMD_GETFIRMWAREVERSION); self.cmd(CMD_SAMCONFIGURATION,b'\\x01\\x00\\x00')
        print("PN532 fw: %d.%d" % (fw[1],fw[2]))
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
    total=(len(ndef)+3)//4
    for i in range(total):
        led.progress(i+1,total)
        nfc.ntag_write_page(4+i,ndef[i*4:i*4+4])
        print('[WRITE_PROGRESS:%d:%d]' % (i+1,total))
        time.sleep_ms(30)
    return True

def write_mifare(nfc,tag,text,led):
    ndef=build_ndef(text)
    while len(ndef)%16!=0: ndef+=b'\\x00'
    total=len(ndef)//16
    writable=[]
    for sec in range(1,16):
        for b in range(3): writable.append(sec*4+b)
    for i in range(min(total,len(writable))):
        block=writable[i]; sector=block//4
        led.progress(i+1,total)
        resel=nfc.detect_tag(timeout=300)
        if not resel: return False
        authed=False
        for key in COMMON_KEYS:
            for kt in [MIFARE_AUTH_A,MIFARE_AUTH_B]:
                if nfc.mifare_auth(tag['uid'],sector*4,key,kt): authed=True; break
            if authed: break
        if not authed: return False
        nfc.mifare_write(block,ndef[i*16:i*16+16])
        print('[WRITE_PROGRESS:%d:%d]' % (i+1,total))
        time.sleep_ms(30)
    return True

def write_once():
    i2c=machine.SoftI2C(sda=machine.Pin(I2C_SDA),scl=machine.Pin(I2C_SCL),freq=100_000)
    led=LEDAnimator(NEOPIXEL,NUM_LEDS); beep=Beeper(BUZZER); led.clear()
    nfc=PN532(i2c,PN532_ADDR); nfc.init()
    frame=0; tag=None; tag_on=False; waiting=False
    while True:
        if not waiting: led.waiting(frame); frame+=1
        detected=nfc.detect_tag(timeout=100)
        if waiting:
            if not detected:
                tag_on=False; waiting=False; tag=None
                print('[CARD_REMOVED]')
                led.clear()
                continue
            ch=_stdin_char()
            if ch in ('y','Y'):
                break
            elif ch in ('n','N'):
                print('[WRITE_CANCELLED]')
                led.clear(); return
        else:
            if detected and not tag_on:
                tag=detected; tag_on=True; waiting=True
                beep.click(); led.fill((0,20,0))
                print('[NFC_FOUND:%s:%s]' % (tag['uid_hex'],tag['tag_type']))
            elif not detected and tag_on:
                tag_on=False; tag=None
        time.sleep_ms(50)
    ok=False
    try:
        if tag['is_ntag']: ok=write_ntag(nfc,tag,TEXT,led)
        elif tag['is_classic']: ok=write_mifare(nfc,tag,TEXT,led)
        else: print('[WRITE_FAILED:Unsupported tag]'); led.clear(); return
    except Exception as e:
        print('[WRITE_FAILED:' + str(e) + ']'); led.failure(); beep.fail(); led.clear(); return
    if ok:
        print('[WRITE_DONE]'); led.success(); beep.success()
    else:
        print('[WRITE_FAILED:Write error]'); led.failure(); beep.fail()
    led.clear()

write_once()
`.trim();
}

// ── REPL listener ─────────────────────────────────────────────────────────────
// Temporarily intercepts uboard.newDataCallback to parse protocol messages.
// Calls onCardFound(uid, tagType) → Promise<bool> when card detected.
// Calls onProgress(current, total) and onStatus(state) for UI updates.

export async function writeNfcTag(uboard, addMsg, text, callbacks = {}) {
    if (!uboard.connected) { addMsg("Connect your board first.", "system"); return false; }
    if (!text) { addMsg("No card text specified.", "system"); return false; }

    const { onCardFound = null, onProgress = null, onStatus = null } = callbacks;
    const script = generateWriteScript(text);

    return new Promise(async (resolve) => {
        const prevCallback = uboard.newDataCallback;
        let buf = '';
        let settled = false;

        function finish(success) {
            if (settled) return;
            settled = true;
            uboard.newDataCallback = prevCallback;
            resolve(success);
        }

        uboard.newDataCallback = async (chunk) => {
            if (prevCallback) await prevCallback(chunk);
            if (settled) return;

            buf += chunk;

            // [NFC_FOUND:uid:tagtype]
            const foundMatch = buf.match(/\[NFC_FOUND:([^:]+):([^\]]*)\]/);
            if (foundMatch) {
                buf = buf.replace(foundMatch[0], '');
                const uid = foundMatch[1];
                const tagType = foundMatch[2];
                if (onStatus) onStatus('found');

                const confirmed = onCardFound
                    ? await onCardFound(uid, tagType)
                    : window.confirm(`${tagType} detected (${uid}). Write "${text}"?`);

                if (confirmed) {
                    if (onStatus) onStatus('writing');
                    await uboard.board.write('y\n');
                } else {
                    await uboard.board.write('n\n');
                    finish(false);
                }
                return;
            }

            // [CARD_REMOVED]
            if (buf.includes('[CARD_REMOVED]')) {
                buf = buf.replace('[CARD_REMOVED]', '');
                if (onStatus) onStatus('scanning');
            }

            // [WRITE_PROGRESS:n:total] — consume all in this chunk
            let pm;
            while ((pm = buf.match(/\[WRITE_PROGRESS:(\d+):(\d+)\]/))) {
                buf = buf.replace(pm[0], '');
                if (onProgress) onProgress(parseInt(pm[1]), parseInt(pm[2]));
            }

            // Terminal states
            if (buf.includes('[WRITE_DONE]')) {
                if (onStatus) onStatus('done');
                finish(true);
            } else if (buf.includes('[WRITE_CANCELLED]')) {
                if (onStatus) onStatus('cancelled');
                finish(false);
            } else if (buf.includes('[WRITE_FAILED')) {
                if (onStatus) onStatus('failed');
                finish(false);
            }
        };

        if (onStatus) onStatus('scanning');
        await uboard.board.write('\x03');
        await sleep(300);
        await uboard.paste(script);
        uboard.focus();
    });
}

// ── Upload slot picker ────────────────────────────────────────────────────────

export function showUploadModal() {
    return new Promise(resolve => {
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

// ── Card-found confirmation popup ─────────────────────────────────────────────

function showCardFoundPopup(uid, tagType, cardText) {
    return new Promise(resolve => {
        const overlay = document.getElementById("card-found-overlay");
        document.getElementById("card-found-info").textContent = tagType + ' · ' + uid;
        document.getElementById("card-found-label").textContent = '"' + cardText + '"';
        overlay.classList.remove("hidden");

        function onWrite()  { cleanup(); overlay.classList.add("hidden"); resolve(true); }
        function onCancel() { cleanup(); overlay.classList.add("hidden"); resolve(false); }
        function cleanup() {
            document.getElementById("btn-card-found-write").removeEventListener("click", onWrite);
            document.getElementById("btn-card-found-cancel").removeEventListener("click", onCancel);
        }

        document.getElementById("btn-card-found-write").addEventListener("click", onWrite);
        document.getElementById("btn-card-found-cancel").addEventListener("click", onCancel);
    });
}

// ── Bundled cards modal (trigger + game cards, written before upload) ─────────

export function showBundledCardsModal(triggerText, gameCards, uboard, addMsg) {
    return new Promise(resolve => {
        const overlay = document.getElementById("nfc-bundle-overlay");
        const list = document.getElementById("nfc-bundle-list");
        list.innerHTML = '';

        const allCards = [
            { text: triggerText, label: 'Trigger — "' + triggerText + '"' },
            ...gameCards.map(c => ({ text: c, label: 'Game card — "' + c + '"' })),
        ];

        allCards.forEach(({ text, label }) => {
            const row = document.createElement("div");
            row.className = "nfc-card-item";

            const labelEl = document.createElement("span");
            labelEl.className = "nfc-card-label";
            labelEl.textContent = label;

            const btn = document.createElement("button");
            btn.className = "btn nfc-btn";
            btn.textContent = "Write Tag";
            btn.dataset.card = text;

            const statusEl = document.createElement("span");
            statusEl.className = "nfc-card-status";

            row.append(labelEl, btn, statusEl);
            list.appendChild(row);

            btn.addEventListener("click", async () => {
                // Disable all buttons while writing
                list.querySelectorAll("button[data-card]").forEach(b => { b.disabled = true; });
                statusEl.innerHTML = '<span class="spinner"></span>';

                const success = await writeNfcTag(uboard, addMsg, text, {
                    onCardFound: (uid, tagType) => showCardFoundPopup(uid, tagType, text),
                    onStatus: (state) => {
                        if (state === 'scanning') statusEl.innerHTML = '<span class="spinner"></span> Scanning...';
                        else if (state === 'found')    statusEl.textContent = 'Card found!';
                        else if (state === 'writing')  statusEl.innerHTML = '<span class="spinner"></span> Writing...';
                        else if (state === 'done')      statusEl.textContent = '✓ Written!';
                        else if (state === 'failed')    statusEl.textContent = '✗ Failed';
                        else if (state === 'cancelled') statusEl.textContent = 'Cancelled';
                    },
                    onProgress: (current, total) => {
                        const pct = Math.round((current / total) * 100);
                        statusEl.innerHTML =
                            '<div class="write-progress-bar">' +
                            '<div class="write-progress-fill" style="width:' + pct + '%"></div>' +
                            '</div>' +
                            '<span class="write-pct">' + pct + '%</span>';
                    },
                });

                // Re-enable buttons that haven't been written yet
                list.querySelectorAll("button[data-card]").forEach(b => {
                    const sibStatus = b.nextElementSibling.textContent;
                    if (sibStatus !== '✓ Written!') b.disabled = false;
                });

                if (!success && statusEl.textContent !== '✓ Written!') {
                    btn.disabled = false;
                }
            });
        });

        overlay.classList.remove("hidden");

        function onDone() { cleanup(); overlay.classList.add("hidden"); resolve(); }
        function onSkip() { cleanup(); overlay.classList.add("hidden"); resolve(); }
        function cleanup() {
            document.getElementById("btn-nfc-bundle-done").removeEventListener("click", onDone);
            document.getElementById("btn-nfc-bundle-skip").removeEventListener("click", onSkip);
        }

        document.getElementById("btn-nfc-bundle-done").addEventListener("click", onDone);
        document.getElementById("btn-nfc-bundle-skip").addEventListener("click", onSkip);
    });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
