import time
import re
from enum import Enum
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice
from hardwarelibrary.motion import SutterDevice
from threading import Thread, RLock
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
    def __init__(self):
        super().__init__("debug", 0xffff, 0xfffe)
        self.errorInitialize = False
        self.errorShutdown = False

    def doInitializeDevice(self):
        if self.errorInitialize:
            raise RuntimeError()

    def doShutdownDevice(self):
        if self.errorShutdown:
            raise RuntimeError()

class DeviceManager:
    _instance = None

    def __init__(self):
        if not hasattr(self, 'devices'):
            self.devices = set()
        if not hasattr(self, 'quitMonitoring'):
            self.quitMonitoring = False
        if not hasattr(self, 'lock'):
            self.lock = RLock()
        if not hasattr(self, 'monitoring'):
            self.monitoring = None
        if not hasattr(self, 'usbDevices'):
            self.usbDevices = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def startMonitoring(self):
        with self.lock:
            if not self.isMonitoring:
                self.quitMonitoring = False
                self.monitoring = Thread(target=self.monitoringLoop, name="DeviceManager-RunLoop")
                NotificationCenter().postNotification(notificationName=DeviceManagerNotification.willStartMonitoring, notifyingObject=self)
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def monitoringLoop(self, duration=1e7):        
        startTime = time.time()
        endTime = startTime + duration
        NotificationCenter().postNotification(DeviceManagerNotification.didStartMonitoring, notifyingObject=self)
        while time.time() < endTime :    
            currentDevices = []
            with self.lock:
                newDevices, newlyDisconnected = self.newlyConnectedAndDisconnectedUSBDevices()
                for newUsbDevice in newDevices:
                    self.usbDeviceConnected(newUsbDevice)
                for oldUsbDevice in newlyDisconnected:
                    self.usbDeviceDisconnected(oldUsbDevice)

                currentDevices.extend(self.devices)

            NotificationCenter().postNotification(DeviceManagerNotification.status, notifyingObject=self, userInfo=currentDevices)

            with self.lock:
                if self.quitMonitoring:
                     break
            time.sleep(0.2)
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

    def handleNotifications(self, notification):
        print(notification.name, notification.userInfo)

    def newlyConnectedAndDisconnectedUSBDevices(self):
        currentlyConnectedDevices = connectedUSBDevices()
        newlyConnected = [ usbDevice for usbDevice in currentlyConnectedDevices if usbDevice not in self.usbDevices]
        newlyDisconnected = [ usbDevice for usbDevice in self.usbDevices if usbDevice not in currentlyConnectedDevices]

        return newlyConnected, newlyDisconnected

    def matchUSBDeviceWithPhysicalDevice(self, usbDevice):
        return DebugPhysicalDevice()

    @property
    def isMonitoring(self):
        with self.lock:
            return self.monitoring is not None
    
    def stopMonitoring(self):
        if self.isMonitoring:
            NotificationCenter().postNotification(DeviceManagerNotification.willStopMonitoring, notifyingObject=self)
            with self.lock:
                self.quitMonitoring = True
            self.monitoring.join()
            self.monitoring = None
        else:
            raise RuntimeError("No monitoring loop running")

    def usbDeviceConnected(self, usbDevice):
        try:
            deviceSerialNumber = usb.util.get_string(usbDevice, usbDevice.iSerialNumber ) 
        except Exception as err:
            deviceSerialNumber = ""
        descriptor = (usbDevice.idVendor, usbDevice.idProduct, deviceSerialNumber)
        NotificationCenter().postNotification(DeviceManagerNotification.usbDeviceDidConnect, notifyingObject=self, userInfo=descriptor)

    def usbDeviceDisconnected(self, usbDevice):
        try:
            deviceSerialNumber = usb.util.get_string(usbDevice, usbDevice.iSerialNumber ) 
        except Exception as err:
            deviceSerialNumber = ""
        descriptor = (usbDevice.idVendor, usbDevice.idProduct, deviceSerialNumber)
        NotificationCenter().postNotification(DeviceManagerNotification.usbDeviceDidDisconnect, notifyingObject=self, userInfo=descriptor)

    def addDevice(self, device):
        NotificationCenter().postNotification(DeviceManagerNotification.willAddDevice, notifyingObject=self, userInfo=device)
        with self.lock:
            self.devices.add(device)
        NotificationCenter().postNotification(DeviceManagerNotification.didAddDevice, notifyingObject=self, userInfo=device)

    def removeDevice(self, device):
        NotificationCenter().postNotification(DeviceManagerNotification.willRemoveDevice, notifyingObject=self, userInfo=device)
        with self.lock:
            self.devices.remove(device)
        NotificationCenter().postNotification(DeviceManagerNotification.didRemoveDevice, notifyingObject=self, userInfo=device)

    def matchPhysicalDevicesOfType(self, deviceClass, serialNumber=None):
        with self.lock:
            matched = []
            for device in self.devices:
                if issubclass(type(device), deviceClass):
                    if serialNumber is not None:
                        regexSerialNumber = serialNumber
                        regMatch = re.match(regexSerialNumber, device.serialNumber)
                        if regMatch is not None:
                            matched.append(device)
                    else:
                        matched.append(device)
            return matched
