# Running on pure micropython
This contains my examples of where to go with pure micropython

1. start with https://micropython.org/download/LEGO_HUB_NO6/
2. Grabbed [this](https://micropython.org/resources/firmware/LEGO_HUB_NO6-20240105-v1.22.1.dfu) and put into boot loader mode with holding the BLE button down while plugging it in and holding it until I got many different colors.
3. Ran `dfu-util --alt 0 -D LEGO_HUB_NO6-20240105-v1.22.1.dfu` from within downloads (since that is where the firmware downloaded)
4. Then I restarted the hub and got the standard “cannot read the hard drive” error - but it all worked. (note: I had to disconnect and reconnect my cable once…)
5. You can get rid of the above error if you do a make of mboot and deploy that as well.