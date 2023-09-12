from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication import *
from .lasersourcedevice import LaserSourceDevice

import re
import time
from threading import Thread, RLock

class CoboltCantTurnOnWithAutostartOn(Exception):
    pass

class CoboltDevice(PhysicalDevice, LaserSourceDevice):

    def __init__(self, bsdPath=None, portPath=None, serialNumber: str = None,
                 idProduct: int = None, idVendor: int = None):

        self.laserPower = 0
        self.requestedPower = 0
        self.interlockState = None
        self.autostart = None
        self.laserSerialNumber = None
        self.isOn = None

        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        PhysicalDevice.__init__(self, serialNumber, idVendor, idProduct)
        LaserSourceDevice.__init__(self)
        self.port = None

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return
    def autostartIsOn(self) -> bool:
        self.doGetAutostart()
        return self.autostart

    def turnAutostartOn(self):
        self.doTurnAutostartOn()

    def turnAutostartOff(self):
        self.doTurnAutostartOff()

    def doInitializeDevice(self): 
        try:
            if self.portPath == "debug":
                self.port = CommunicationPort(port=CoboltDebugSerial())
            else:
                self.port = SerialPort(portPath=self.portPath)
            
            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port {0}".format(self.portPath))

            self.port.open()
            self.doGetLaserSerialNumber()
            self.doGetAutostart()
            self.doTurnAutostartOn()
            self.doGetInterlockState()
            self.doGetPower()
        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize()
        except PhysicalDeviceUnableToInitialize as error:
            raise error
        

    def doShutdownDevice(self):
        self.port.close()
        self.port = None
        return

    def doGetInterlockState(self) -> bool:
        value = self.port.writeStringExpectMatchingString('ilk?\r', replyPattern='(0|1)')
        self.interlockState = bool(value)
        return self.interlockState

    def doGetLaserSerialNumber(self) -> str:
        self.laserSerialNumber = self.port.writeStringReadFirstMatchingGroup('sn?\r', replyPattern='(\\d+)')

    def doGetOnOffState(self) -> bool:
        value = self.port.writeStringExpectMatchingString('l?\r', replyPattern='(0|1)')
        self.isOn = (int(value) == 1)
        return self.isOn        

    def doTurnOn(self):
        if not self.doGetAutostart():
            self.port.writeStringExpectMatchingString('l1\r', replyPattern='OK')
        else:
            raise CoboltCantTurnOnWithAutostartOn()

    def doTurnOff(self):
        self.port.writeStringExpectMatchingString('l0\r', replyPattern='OK')

    def doGetAutostart(self) -> bool:
        value = self.port.writeStringReadFirstMatchingGroup('@cobas?\r', '([1|0])')
        self.autostart = (int(value) == 1)
        return self.autostart

    def doTurnAutostartOn(self):
        self.port.writeStringExpectMatchingString('@cobas 1\r', 'OK')
        self.autostart = True

    def doTurnAutostartOff(self):
        self.port.writeStringExpectMatchingString('@cobas 0\r', 'OK')
        self.autostart = False

    def doSetPower(self, powerInWatts) -> float:
        command = 'p {0:0.3f}\r'.format(powerInWatts)
        self.port.writeStringExpectMatchingString(command, replyPattern='OK')
        actualPower = 0
        acceptableDifference = 0.1 * powerInWatts
        for i in range(10): # It is not an error if we don't converge
            actualPower = self.doGetPower()
            if abs(actualPower - powerInWatts) < acceptableDifference:
                break
            else:
                time.sleep(0.1)
        return actualPower

    def doGetPower(self) -> float:
        value = self.port.writeStringReadFirstMatchingGroup('pa?\r', replyPattern='(\\d.\\d+)')
        return float(value)

class CoboltDebugSerial:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.power = 0.1
        self.isOn = 0
        self.requestedPower = 0
        self.autostart = 1
        self._isOpen = True

    @property
    def is_open(self):
        return self._isOpen
    
    def open(self):
        with globalLock:
            if self._isOpen:
                raise IOError("port is already open")
            else:
                self._isOpen = True

        return

    def close(self):
        with globalLock:
            self._isOpen = False

        return

    def flush(self):
        return

    def read(self, length) -> bytearray:
        with globalLock:
            data = bytearray()
            for i in range(0, length):
                if len(self.outputBuffer) > 0:
                    byte = self.outputBuffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data


    def write(self, data:bytearray) -> int :
        with globalLock:
            string = data.decode('utf-8', 'replace')

            match = re.search("pa\\?", string)
            if match is not None:
                replyData = bytearray("{0:0.4f}\r\n".format(self.power), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("p\\?", string)
            if match is not None:
                replyData = bytearray("{0:0.4f}\r\n".format(self.requestedPower), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("p (\\d+\\.?\\d+)\r", string)
            if match is not None:
                requestedPower = float(match.groups()[0])
                process = Thread(target=increasePowerSlowlyInBackground, 
                                 kwargs=dict(port=self,
                                             endPower=requestedPower,
                                             duration=1.0))
                process.start() # will complete in the background
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l\\?\r", string)
            if match is not None:
                replyData = bytearray("{0}\r\n".format(self.isOn), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l1\r", string)
            if match is not None:
                replyData = bytearray()
                if self.autostart == 1:
                    replyData = bytearray("Syntax error: not allowed in autostart mode\r\n", encoding='utf-8')
                else:
                    self.isOn = 1
                    replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l0\r", string)
            if match is not None:
                self.isOn = 0
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)


            match = re.search("sn\\?\r", string)
            if match is not None:
                replyData = bytearray("123456\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas 1\r", string)
            if match is not None:
                if self.autostart == 0:
                    self.isOn = 0
                else:
                    pass
                self.autostart = 1
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas 0\r", string)
            if match is not None:
                self.autostart = 0
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas\\?\r", string)
            if match is not None:
                replyData = bytearray("{0}\r\n".format(self.autostart), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)


            match = re.search("ilk\\?\r", string)
            if match is not None:
                replyData = bytearray("1\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)

                return len(data)

            # Error (string already includes \n)
            replyData = bytearray("Syntax error: {0}\n".format(string), encoding='utf-8')
            self.outputBuffer.extend(replyData)

        return len(data)


def increasePowerSlowlyInBackground(port, endPower, duration):
    actualPower = port.power
    delta = (endPower - actualPower)/10.0
    for i in range(10):
        with globalLock:
            try:
                port.power = actualPower + delta * (i+1)
            except:
                print("Unable to set power")
        time.sleep(0.05)
    port.power = endPower

