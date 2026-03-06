from utilities.nfc import NFC

def on_detect(uid):
    print(f'detected {uid}')

def on_remove(uid):
    print(f'removed {uid}')

nfc = NFC(on_detect, on_remove)
print(nfc.version())

while nfc.rf is not None:
    try:
        nfc.read(timeout = 1.0)
    except Exception as e:
        nfc.reset()
        