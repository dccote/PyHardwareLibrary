import time
import re
from enum import Enum
from typing import NamedTuple
from threading import Thread, RLock
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice, SutterDevice
from hardwarelibrary.spectrometers import Spectrometer
from hardwarelibrary.powermeters import PowerMeterDevice, IntegraDevice
from hardwarelibrary.communication.diagnostics import *

class DeviceManagerNotification(Enum):
    status              = "status"
    willStartMonitoring = "willStartMonitoring"
    didStartMonitoring  = "didStartMonitoring"
    willStopMonitoring  = "willStopMonitoring"
    didStopMonitoring   = "didStopMonitoring"

    willAddDevice       = "willAddDevice"
    didAddDevice        = "didAddDevice"
    willRemoveDevice    = "willRemoveDevice"
    didRemoveDevice     = "didRemoveDevice"
    usbDeviceDidConnect = "usbDeviceDidConnect"
    usbDeviceDidDisconnect = "usbDeviceDidDisconnect"

class DebugPhysicalDevice(PhysicalDevice):
    classIdVendor = 0xffff
    classIdProduct = 0xfffe
    def __init__(self):
        super().__init__("debug", DebugPhysicalDevice.classIdProduct, DebugPhysicalDevice.classIdVendor)
        self.errorInitialize = False
        self.errorShutdown = False

    def doInitializeDevice(self):
        if self.errorInitialize:
            raise RuntimeError("This error in initializeDevice was programmed for testing")

    def doShutdownDevice(self):
        if self.errorShutdown:
            raise RuntimeError("This error in shutdownDevice was programmed for testing")


class USBDeviceDescriptor:

    @classmethod
    def fromUSBDevice(cls, usbDevice):
        idProduct = usbDevice.idProduct
        idVendor = usbDevice.idVendor
        serialNumber = None
        try:
            serialNumber = usb.util.get_string(usbDevice, usbDevice.iSerialNumber)
        except Exception as err:
            serialNumber = None

        return USBDeviceDescriptor(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor, usbDevice=usbDevice)

    @classmethod
    def fromProductVendor(cls, serialNumber=None, idProduct=None, idVendor=None):
        devices = connectedUSBDevices(serialNumber, idProduct, idVendor)
        usbDevice = None
        if len(devices) == 1:
            usbDevice = devices[0]

        return USBDeviceDescriptor(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor, usbDevice=usbDevice)

    def __init__(self, serialNumber=None, idProduct=None, idVendor=None, usbDevice=None):
        self.serialNumber = serialNumber
        if self.serialNumber is None or serialNumber == "*":
            self.serialNumberPattern = ".?" # at least one character
        else:
            self.serialNumberPattern = self.serialNumber

        self.idProduct = idProduct
        self.idVendor = idVendor
        self.usbDevice = usbDevice # should be unconfigured?

    def __eq__(self, rhs):
        if self.serialNumber != rhs.serialNumber:
            return False
        if self.idProduct != rhs.idProduct:
            return False
        if self.idVendor != rhs.idVendor:
            return False
        if self.usbDevice != rhs.usbDevice:
            return False
        return True

    def matchesPhysicalDevice(self, device):
        if self.idProduct != device.idProduct:
            return False
        if self.idVendor != device.idVendor:
            return False
        if re.match(self.serialNumber, device.serialNumber, re.IGNORECASE) is not None:
            return False

        return True

class DeviceManager:
    _instance = None

    def destroy(self):
        dm = DeviceManager()
        DeviceManager._instance = None
        del(dm)

    def __init__(self):
        if not hasattr(self, 'devices'):
            self.devices = set()
        if not hasattr(self, 'quitMonitoring'):
            self.quitMonitoring = False
        if not hasattr(self, 'quitServer'):
            self.quitServer = False
        if not hasattr(self, 'lock'):
            self.lock = RLock()
        if not hasattr(self, 'monitoring'):
            self.monitoring = None
        if not hasattr(self, 'server'):
            self.server = None
        if not hasattr(self, 'usbDevices'):
            self.usbDevices = []
        if not hasattr(self, 'usbDeviceDescriptors'):
            self.usbDeviceDescriptors = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def __del__(self):
        for device in self.devices:
            device.shutdownDevice()

    def startMonitoring(self):
        with self.lock:
            if not self.isMonitoring:
                self.quitMonitoring = False
                self.monitoring = Thread(target=self.monitoringLoop, name="DeviceManager-RunLoop")
                NotificationCenter().postNotification(notificationName=DeviceManagerNotification.willStartMonitoring, notifyingObject=self)
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def startServer(self):
        with self.lock:
            if not self.isServing:
                self.quitServer = False
                self.server = Thread(target=self.serverLoop, name="DeviceManager-ServerLoop")
                self.server.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def updateConnectedDevices(self) -> list:
        currentDevices = []
        with self.lock:
            newDevices, newlyDisconnected = self.newlyConnectedAndDisconnectedUSBDevices()
            for newUsbDevice in newDevices:
                self.usbDeviceConnected(newUsbDevice)
            for oldUsbDevice in newlyDisconnected:
                self.usbDeviceDisconnected(oldUsbDevice)

            currentDevices.extend(self.devices)

        return currentDevices

    def monitoringLoop(self, duration=1e7):        
        startTime = time.time()
        endTime = startTime + duration
        NotificationCenter().postNotification(DeviceManagerNotification.didStartMonitoring, notifyingObject=self)
        while time.time() < endTime :    
            currentDevices = self.updateConnectedDevices()
            NotificationCenter().postNotification(DeviceManagerNotification.status, notifyingObject=self, userInfo=currentDevices)

            with self.lock:
                if self.quitMonitoring:
                     break
            time.sleep(0.3)
        NotificationCenter().postNotification(DeviceManagerNotification.didStopMonitoring, notifyingObject=self)

    def showNotifications(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.status)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.willStartMonitoring)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.didStartMonitoring)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.willStopMonitoring)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.didStopMonitoring)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.willAddDevice)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.didAddDevice)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.willRemoveDevice)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.didRemoveDevice)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.usbDeviceDidConnect)
        nc.addObserver(self, self.handleNotifications, DeviceManagerNotification.usbDeviceDidDisconnect)

    def serverLoop(self):
        import socket,os
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        sock.bind(('127.0.0.1', 12345))  
        sock.listen(5)  
        while True:  
            connection,address = sock.accept()  
            c = None
            buffer = []
            while c != b'\n' and c != b'\r':
                c = connection.recv(1)
                buffer.append(c)
                print(c)

            print(buffer)
            connection.send(b"I did receive something")            
        
        connection.close()


    def handleNotifications(self, notification):
        print(notification.name, notification.userInfo)

    def newlyConnectedAndDisconnectedUSBDevices(self):
        currentlyConnectedDevices = connectedUSBDevices()
        newlyConnected = [ usbDevice for usbDevice in currentlyConnectedDevices if usbDevice not in self.usbDevices]
        newlyDisconnected = [ usbDevice for usbDevice in self.usbDevices if usbDevice not in currentlyConnectedDevices]
        self.usbDevices = currentlyConnectedDevices

        return newlyConnected, newlyDisconnected

    @property
    def isMonitoring(self):
        with self.lock:
            return self.monitoring is not None

    @property
    def isServing(self):
        with self.lock:
            return self.server is not None
    
    def stopMonitoring(self):
        if self.isMonitoring:
            NotificationCenter().postNotification(DeviceManagerNotification.willStopMonitoring, notifyingObject=self)
            with self.lock:
                self.quitMonitoring = True
            self.monitoring.join()
            self.removeAllDevices()
            self.monitoring = None
        else:
            raise RuntimeError("No monitoring loop running")

    def usbDeviceConnected(self, usbDevice):
        descriptor = USBDeviceDescriptor.fromUSBDevice(usbDevice)
        NotificationCenter().postNotification(DeviceManagerNotification.usbDeviceDidConnect, notifyingObject=self, userInfo=descriptor)
        if descriptor not in self.usbDeviceDescriptors:
            self.usbDeviceDescriptors.append(descriptor)

        candidates = PhysicalDevice.candidates(descriptor.idVendor, descriptor.idProduct)
        for candidateClass in candidates:
            # This may throw if incompatible
            deviceInstance = candidateClass(serialNumber=descriptor.serialNumber,
                                            idProduct=descriptor.idProduct,
                                            idVendor=descriptor.idVendor)
            deviceInstance.initializeDevice()
            deviceInstance.shutdownDevice()
            self.addDevice(deviceInstance)

    def usbDeviceDisconnected(self, usbDevice):
        descriptor = None
        for aDescriptor in self.usbDeviceDescriptors:
            if aDescriptor.usbDevice == usbDevice:
                descriptor = aDescriptor
                break
        if descriptor is None:
            print("Unable to find descriptor matching {0}".format(usbDevice))

        NotificationCenter().postNotification(DeviceManagerNotification.usbDeviceDidDisconnect, notifyingObject=self, userInfo=descriptor)

        currentDevices = list(self.devices)
        for device in currentDevices:
            if descriptor.matchesPhysicalDevice(device):
                self.removeDevice(device)

    def addDevice(self, device):
        with self.lock:
            NotificationCenter().postNotification(DeviceManagerNotification.willAddDevice, notifyingObject=self, userInfo=device)
            self.devices.add(device)
            NotificationCenter().postNotification(DeviceManagerNotification.didAddDevice, notifyingObject=self, userInfo=device)

    def removeAllDevices(self):
        with self.lock:
            devicesToRemove = set(self.devices)
            for device in devicesToRemove:
                try:
                    device.shutdownDevice()
                except Exception as err:
                    print(err)
                self.removeDevice(device)

    def removeDevice(self, device):
        with self.lock:
            NotificationCenter().postNotification(DeviceManagerNotification.willRemoveDevice, notifyingObject=self,
                                                  userInfo=device)
            self.devices.remove(device)
            NotificationCenter().postNotification(DeviceManagerNotification.didRemoveDevice, notifyingObject=self, userInfo=device)

    def matchPhysicalDevicesOfType(self, deviceClass, serialNumber=None):
        with self.lock:
            matched = []
            for device in self.devices:
                if issubclass(type(device), deviceClass):
                    if serialNumber is not None:
                        regexSerialNumber = serialNumber
                        regMatch = re.match(regexSerialNumber, device.serialNumber, re.IGNORECASE)
                        if regMatch is not None:
                            matched.append(device)
                    else:
                        matched.append(device)
            return matched

    def linearMotionDevices(self):
        return self.matchPhysicalDevicesOfType(deviceClass=LinearMotionDevice)

    def anyLinearMotionDevice(self):
        devices = self.linearMotionDevices()
        if len(devices) == 0:
            return None
        return devices[0]

    def spectrometerDevices(self):
        return self.matchPhysicalDevicesOfType(deviceClass=Spectrometer)

    def anySpectrometerDevice(self):
        devices = self.spectrometerDevices()
        if len(devices) == 0:
            return None
        return devices[0]

    def powerMeterDevices(self):
        return self.matchPhysicalDevicesOfType(deviceClass=PowerMeterDevice)

    def anyPowerMeterDevice(self):
        devices = self.powerMeterDevices()
        if len(devices) == 0:
            return None
        return devices[0]

    def sendCommand(self, commandName, deviceIdentifier=0):
        DeviceManager().updateConnectedDevices()
        device = list(self.devices)[deviceIdentifier]

        if re.search("^list$", commandName, re.IGNORECASE) is not None:
            print(self.devices)
        elif device.state == DeviceState.Ready:
            command = device.commands[commandName]
            command.send(port=device.port)
            return (commandName, command.text, command.matchGroups)
        else:
            print("Device {0} is not Ready: call initializeDevice()".format(device))

