import Board from 'https://cdn.jsdelivr.net/npm/micro-repl@0.5.2/serial.js';

const FIFO_SIZE = 10000;

export class uRepl {
    constructor() {
        this.connected = false;
        this.terminal = null;
        this.buffer = '';
        this.disconnectCallback = null;
        this.newDataCallback = null;

        this.board = new Board({
            baudRate: 115200,
            dataType: "string",
            onconnect: () => this._onConnect(),
            ondisconnect: () => this._onDisconnect(),
            ondata: (chunk) => this._onData(chunk),
            onresult: JSON.parse,
            onerror: window.alert,
            fontSize: '14',
            fontFamily: 'Courier New',
            theme: {
                background: "#f8f9fa",
                foreground: "#1f2937",
            },
        });
    }

    async _onData(chunk) {
        this.buffer += chunk;
        this.buffer = this.buffer.slice(-FIFO_SIZE);
        if (this.newDataCallback) await this.newDataCallback(chunk);
    }

    _onConnect() {
        console.log('connected');
        this.connected = true;
        this.terminal = this.board.terminal;
    }

    async _onDisconnect() {
        this.connected = false;
        this.terminal = null;
        if (this.disconnectCallback) await this.disconnectCallback();
    }

    async paste(payload) {
        return await this.board.paste(payload);
    }

    async eval(payload) {
        return await this.board.eval(payload);
    }

    focus() {
        if (this.terminal) this.terminal.focus();
    }
}
