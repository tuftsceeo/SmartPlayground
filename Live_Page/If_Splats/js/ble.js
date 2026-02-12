class BLEDevice {
    constructor() {
        this.device = null;
        this.server = null;
        this.service = null;
        this.writeCharacteristic = null;
        this.notifyCharacteristic = null;
        this.callback = null;
    }

    async connect(name, serviceUUID, writeUUID, notifyUUID) {
        try {
            var filters;
            if (name == '') 
             {filters =[{services: serviceUUID}]}
            else 
             {filters = [{ name: name }]};
            console.log(filters);
            this.device = await navigator.bluetooth.requestDevice(
                {filters: filters,
                optionalServices: [serviceUUID]}
            );
            this.server = await this.device.gatt.connect();
            this.service = await this.server.getPrimaryService(serviceUUID);
            this.writeCharacteristic = await this.service.getCharacteristic(writeUUID);
            this.notifyCharacteristic = await this.service.getCharacteristic(notifyUUID);
            this.handleNotification = this.handleNotification.bind(this);
            await this.notifyCharacteristic.startNotifications();
            this.notifyCharacteristic.addEventListener('characteristicvaluechanged',
                this.handleNotification);
        } catch (error) {
            console.error('Error connecting:', error);
        }
    }

    handleNotification(event) {
        const value = event.target.value;
        const data = new Uint8Array(value.buffer);
        if (this.callback) {this.callback(data)};
    }

    async write(data) {
        if (!this.writeCharacteristic) {
            console.error('Not connected to device');
            return;
        }
        try {
            const bytes = new Uint8Array(data);
            await this.writeCharacteristic.writeValue(bytes);
            console.log('Sent:', bytes);
        } catch (error) {
            console.error('Error writing:', error);
        }
    }

    disconnect() {
        if (this.device && this.device.gatt.connected) {
            this.device.gatt.disconnect();
        }
    }
}

export const myBLE = new BLEDevice();
