from .communicationport import *
from .serialport import SerialPort
from .usbport import USBPort
from .diagnostics import USBParameters, DeviceCommand, USBDeviceDescription
from .debugport import DebugPort
from .echoport import DebugEchoPort
from .socketport import SocketPort
import usb.backend.libusb1
import platform
from pathlib import *
import os

def validateUSBBackend():
    backend = usb.backend.libusb1.get_backend()
    if backend is not None:
        try:
            usb.core.find(backend=backend)
            return
        except:
            pass
 
    libusbPath = None
    candidates = []
    if platform.system() == 'Windows':
        rootHardwareLibrary = PureWindowsPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/MS64/libusb-1.0.dll'),
                         rootHardwareLibrary.joinpath('communication/libusb/MS32/libusb-1.0.dll')]
    elif os.name == 'Darwin':
        rootHardwareLibrary = PurePosixPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/Darwin/libusb-1.0.0.dylib')]
    else:
        print('Cannot validate libusb backend.')

    for libpath in candidates:
        if os.path.exists(libpath):
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: "{0}".format(libpath))
            if backend is not None:
                try:
                    usb.core.find(backend=backend)
                    break
                except:
                    pass
        else:
            print("File does not exist {0}".format(libpath))


validateUSBBackend()