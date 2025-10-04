from pyscript import document, when, window
import json, asyncio

try:
    window.navigator.serial.requestPort
except:
    window.alert('you have to use Chrome to talk over serial')


RS232Style = '''
<style>
body {
    font-family: Arial, sans-serif;
}
.input {
    color:#0000FF;
    font-size: 18px;
    border: none;
    background-color:lightlightgray;
}

.py-editor-box, .mpy-editor-box {
    max-height: 300px;
    margin-left: 10px;
    margin-right: 10px;
    overflow: auto;
    border: 1px solid #ccc;
    border-radius: 10px 10px 10px 10px;
    background-color: white;
}

.repl-box {
    margin-bottom: 10px;
    margin-left: 10px;
    margin-right: 10px;
    overflow: auto;
    border: 1px solid #ccc;
    border-radius: 0 10px 10px 0px;
    background-color: white;
}

.parent{
    display: grid;
    height: 55vh;
    width: 95%;
    overflow: hidden;
    border: 1px solid #ccc;
    border-radius: 10px;
    background-color: white;
    margin-left: 10px;
    padding: 10px;
    grid-template-columns: 50% 5px 50%; /* Left column, resizer, right column */
}

.child {
    display: grid;
    grid-template-rows: auto 1fr;
    height: 100%;
    margin: 2px;
    box-sizing: border-box;
    overflow: hidden;
    overflow_y: auto;
}

.btndiv {
    margin: 10px;
    display: inline-block;
    grid-row: 1;
    height: auto;
}

.resizer {
  background-color: whitesmoke;
  border: 1px solid #ccc;
  cursor: col-resize;  /* Cursor changes when hovering over the resizer */
  width: 5px;         /* Resizer width */
}

.info {
    width: 95%;
    margin: 10px;
}
</style>
'''

RS232HTML = '''   
<h3 id='main_title{num}'>Serial Terminal Setup</h3>
    <div id='REPL{num}' class = 'parent'>
        <div id = 'left{num}' class = 'child'>
            <div id = 'left_btns{num}' class = 'btndiv'>
                <input type="checkbox" id="freshStart{num}" checked>
                <label for="freshStart{num}"> reset</label>
                <button id="connect{num}"  class = 'button'>connect up</button>
                <input id = 'title{num}' maxlength = 50 type='text' value = '' class = 'input'>
                <br><br>
                <button id="run{num}"      class = 'button'>run</button>
                <button id="run_main{num}" class = 'button'>run as main.py</button>
                <button id="upload{num}"   class = 'button'>upload code</button>
                <button id="reset{num}"    class = 'button'>reset board</button>

                <button id="ble_load{num}"   class = 'button'>load BLE libraries</button>
                <button id="ble_direct{num}" class = 'button'>Sample BLE code</button>

            </div>
            <script id='mpCode{num}' type="mpy-editor" >
                # Some micropython code here
            </script>
        </div>
        <div id="resizer{num}" class = 'resizer'> </div>
        <div id = 'right{num}' class = 'child'>
            <div id = 'right_btns{num}'    class = 'btndiv'>
                <select name="list_files" id="list_files{num}"> </select>
                <button id="download{num}" class = 'button'>Grab remote code</button> 
                <button id="clear{num}"    class = 'button'>Clear</button> 
                <button id="CtrlC{num}"    class = 'button'>CtrlC</button> 
                <button id="delete{num}"   class = 'button'>Delete remote code</button> 
                <button id="re_list{num}"  class = 'button'>Get List</button> 
            </div>
            <div id="repl{num}" class = 'repl-box'></div>
        </div>
    </div>
'''

# https://cdn.jsdelivr.net/npm/micro-repl@0.5.2/serial.js

from pyscript import window, document
from pyscript.js_modules.micro_repl import default as Board
import json, asyncio

FIFO_SIZE = 10000

list_code = '''
import os
def listdir(directory):
    result = set()
    def _listdir(dir_or_file):
        try:
            children = os.listdir(dir_or_file)
        except OSError:
            os.stat(dir_or_file)
            result.add(dir_or_file)
        else:
            if children:
                for child in children:
                    if dir_or_file == '/':
                        next = dir_or_file + child
                    else:
                        next = dir_or_file + '/' + child
                    _listdir(next)
            else:
                result.add(dir_or_file)
    _listdir(directory)
    return sorted(result)

listdir('/')
'''

class uRepl():
    def __init__(self, baudrate = 115200, buffer_size = 256):

        self.connected = False
        self.terminal = None
        self.disconnect_callback = None
        self.newData_callback = None
        self.buffer = ''
        self.buffer_size = buffer_size
        #self.update(0)
        self.path = None
        self.board = Board({
            "baudRate": baudrate,
            "dataType": "string",
            "onconnect": self.on_connect,
            "ondisconnect": self.on_disconnect,
            "ondata": self.on_data,
            "onresult": json.loads,
            "onerror": window.alert,
            "fontSize": '24',
            "fontFamily": 'Courier New',
            "theme": {
                "background": "white",
                "foreground": "black",
            },
        })

    async def on_data(self, chunk):
        self.buffer += chunk
        self.buffer = self.buffer[-FIFO_SIZE:]
        if self.newData_callback: await self.newData_callback(chunk)
    
    def on_connect(self):
        window.console.log('connected')
        self.connected = True
        self.terminal = self.board.terminal

    async def on_disconnect(self):
        self.connected = False
        #self.terminal.reset()
        self.terminal = None
        if self.disconnect_callback:  
            await self.disconnect_callback()

    async def on_reset(self, error):
        self.reset.disabled = True
        await self.board.reset()
        self.reset.disabled = False

    async def eval(self, payload, hidden=False):
        return await self.board.eval(payload, hidden=hidden)

    async def paste(self,payload, hidden=False):
        return await self.board.paste(payload, hidden=hidden)

    def focus(self):
        self.terminal.focus()

    async def getList(self, list_files = None, desired = "hubname"):
        info = None
        if self.connected:
            window.console.log('getting file listing')
            array = await self.eval(list_code, hidden = True)
            if list_files:
                list_files.options.length = 0
                if array:
                    for name in array:
                        if name.find('/.') == 0:# not '.py' in name or name.find('/.') == 0:
                            continue
                        if desired in name:
                            info = name
                        option = document.createElement('option')
                        option.text = name
                        option.value = name
                        list_files.add(option)
        return info

read_code = """
f = open('%s', "rb")
result = f.read().decode('utf-8')
f.close()
result
"""

class CEEO_RS232():
    def __init__(self, divName, suffix = '', myCSS = False, default_code = None):
        self.hub = ''
        self.suffix = suffix
        self.uboard = uRepl()
        self.rs232div = document.getElementById(divName)
        if myCSS:
            self.rs232div.innerHTML = RS232HTML.format(num = self.suffix)
        else:
            self.rs232div.innerHTML = RS232Style + RS232HTML.format(num = self.suffix)
        
        self.connect    = document.getElementById(f'connect{self.suffix}')
        self.list_files = document.getElementById(f'list_files{self.suffix}')
        self.python     = document.getElementById(f'mpCode{self.suffix}')
        
        self.sampleCode = document.getElementById(f'ble_direct{self.suffix}')
        self.sampleCode.onclick = self.on_ble_direct

        self.connect.onclick = self.on_connect
        self.uboard.disconnect_callback = self.on_disconnect
        document.getElementById(f'download{self.suffix}').onclick = self.on_download
        document.getElementById(f'clear{self.suffix}').onclick = self.on_clear
        document.getElementById(f'CtrlC{self.suffix}').onclick = self.send_CtrlC
        document.getElementById(f're_list{self.suffix}').onclick = self.re_list
        document.getElementById(f'delete{self.suffix}').onclick = self.delete_code
        document.getElementById(f'run{self.suffix}').onclick = self.on_run
        document.getElementById(f'run_main{self.suffix}').onclick = self.on_run_main
        document.getElementById(f'title{self.suffix}').onclick = self.on_title
        document.getElementById(f'upload{self.suffix}').onclick = self.on_upload
        document.getElementById(f'reset{self.suffix}').onclick = self.on_reset
        document.getElementById(f'ble_load{self.suffix}').onclick = self.on_ble_load

        document.getElementById(f'resizer{self.suffix}').onmousedown = self.on_resize
        document.getElementById(f'REPL{self.suffix}').onmousemove = self.movebar
        document.getElementById(f'REPL{self.suffix}').onmouseleave = self.stopbar
        document.getElementById(f'REPL{self.suffix}').onmouseup = self.stopbar

        self.python.code = default_code
        self.python.handleEvent = self.handle_board
        

    async def on_connect(self, event):
        if self.uboard.connected:
            await self.uboard.board.disconnect()
            await self.on_disconnect()
        else:
            stop = document.getElementById(f'freshStart{self.suffix}').checked
            name = await self.uboard.board.connect(f'repl{self.suffix}',stop)  # False if you want to see existing code
            window.console.log(name)
            if not name:
                return
            for i in range(10):
                self.uboard.board.write('\x02')
                if self.uboard.connected: 
                    break
                await asyncio.sleep(0.1)
            if self.uboard.connected:
                self.connect.innerText = 'disconnect'
                if stop:
                    window.console.log(self.uboard.board.name)
                    await self.re_list(None)
                    
    async def on_disconnect(self):
        self.connect.innerText = 'connect up'
        self.list_files.options.length = 0
        document.getElementById(f'title{self.suffix}').value = ''
        self.uboard.buffer = ''

    async def on_download(self, event):
        if self.uboard.connected:
            result = await self.uboard.eval(read_code % self.list_files.value, hidden = True)
            self.python.code = result
    
    def on_clear(self, event):
        if self.uboard.connected:
            self.uboard.board.terminal.clear()
    
    async def send_CtrlC(self, event):
        if self.uboard.connected:
            await self.uboard.board.write('\x03')

    async def re_list(self, event):
        if self.uboard.connected:
            self.hub = await self.uboard.getList(self.list_files,'hubname')
            window.console.log(self.hub)
            if self.hub:
                result = await self.uboard.eval(read_code % self.hub,hidden = True)
                window.console.log(result)
                document.getElementById(f'title{self.suffix}').value = result
    
    async def delete_code(self, event):
        result = await self.uboard.paste(f"""
            import os
            os.remove({json.dumps(self.list_files.value)})
        """)
        await self.uboard.getList(self.list_files)
        return result
    
    async def on_run(self, event):
        if self.uboard.connected:
            await self.uboard.paste(self.python.code)
            self.uboard.focus()
        
    async def on_run_main(self, event):
        if self.uboard.connected:
            success = await self.uboard.board.upload('main.py', self.python.code)
            await self.uboard.board.reset()
            self.uboard.focus()

    async def on_ble_load(self, event):
        if self.uboard.connected:
            import espConnectToPage
            success = await self.uboard.board.upload('BLE_CEEO.py', espConnectToPage.code)
            await self.uboard.board.reset()
            self.uboard.focus()

    async def on_ble_direct(self, event):
        import bleexample
        self.python.code = bleexample.code

    async def on_spike_wave(self, event):
        import spikeexample
        self.python.code = spikeexample.code

    async def on_reset(self, event):
        if self.uboard.connected:
            await self.uboard.board.reset()
            self.uboard.focus()

    async def on_upload(self, event):
        if self.uboard.connected:
            code = self.python.code
            path = window.prompt('What do you want the filename to be on the processor?',self.list_files.value)
            if path:
                name = path +'.py' if not ('.' in path) else path
                success = await self.uboard.board.upload(name, code)
                await self.uboard.getList(self.list_files) 
                self.list_files.value = f'/{name}'
            self.uboard.focus()

    async def on_title(self, event):
        if self.uboard.connected:
            name = event.target.value
            success = window.confirm(f'Did you want to change the name of your processor to {name}?')      
            if success:
                if self.hub:
                    status = await self.uboard.board.upload(self.hub,name)
                else:
                    status = await self.uboard.board.upload('./hubname',name)
                window.console.log(self.uboard.board.name)
                await self.re_list(None)    

    def on_resize(self, event):
        window.console.log('down')
        document.body.style.cursor = 'col-resize'
        document.body.style.userSelect = 'none'

    def movebar(self, event):
        parent = document.getElementById(f'REPL{self.suffix}')
        if document.body.style.cursor == 'col-resize':
            containerRect = parent.getBoundingClientRect()
            newLeftWidth = ((event.clientX - containerRect.left) / containerRect.width) * 100
            newRightWidth = 100 - newLeftWidth
            parent.style.gridTemplateColumns = f'{newLeftWidth}% 10px {newRightWidth}%'

    def stopbar(self, event):
        document.body.style.cursor = ''       # Reset cursor
        document.body.style.userSelect = ''   # Allow text selection again
        
    async def handle_board(self, event):
        code = event.code
        if self.uboard.connected:
            await self.uboard.paste(code)
            self.uboard.focus()
            return False  # return False to avoid executing on browser
        else:
            return True
 

