import usb.core
import usb.util

for bus in usb.busses():
    usbDevices = usb.core.find(find_all=True, idVendor=0xd4d)
    for dev in usbDevices:
	    print(dev)

