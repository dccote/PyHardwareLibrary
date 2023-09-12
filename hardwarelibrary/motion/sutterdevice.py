from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.linearmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import DebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.

class SutterDevice(LinearMotionDevice):
    classIdVendor = 4930
    classIdProduct = 1

    def __init__(self, serialNumber: str = None):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self.port = None
        self.nativeStepsPerMicrons = 16

        # All values are in native units (i.e. microsteps)
        self.xMinLimit = 0
        self.yMinLimit = 0
        self.zMinLimit = 0
        self.xMaxLimit = 25000*16
        self.yMaxLimit = 25000*16
        self.zMaxLimit = 25000*16

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self): 
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor, idProduct=self.idProduct, serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Sutter Device connected")

                self.port = SerialPort(portPath=portPath)
                self.port.open(baudRate=128000, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port {0}".format(portPath))

            self.positionInMicrosteps()

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def sendCommandBytes(self, commandBytes):
        """ The function to write a command to the endpoint. It will initialize the device 
        if it is not alread initialized. On failure, it will warn and shutdown."""
        if self.port is None:
            self.initializeDevice()
        
        time.sleep(0.1)
        nBytesWritten = self.port.writeData(commandBytes)
        if nBytesWritten != len(commandBytes):
            raise Exception(f"Unable to send command {commandBytes} to device.")

    def readReply(self, size, format) -> tuple:
        """ The function to read a reply from the endpoint. It will initialize the device 
        if it is not already initialized. On failure, it will warn and shutdown. 
        It will unpack the reply into a tuple.
        """
        if format is None:
            raise Exception("You must provide a format for unpacking in readReply")

        if self.port is None:
            self.initializeDevice()

        time.sleep(0.1)
        replyBytes = self.port.readData(size)
        if len(replyBytes) != size:
            raise Exception(f"Not enough bytes read in readReply {replyBytes}")

        # print(replyBytes, format)
        # print(unpack(format, replyBytes))
        return unpack(format, replyBytes)

    def positionInMicrosteps(self) -> (int, int, int):  # for compatibility
        return self.doGetPosition()

    def doGetPosition(self) -> (int, int, int):
        """ Returns the position in microsteps """
        commandBytes = pack('<cc', b'C', b'\r')
        self.sendCommandBytes(commandBytes)
        (x, y, z) = self.readReply(size=14, format='<xlllx')

        return (x, y, z)

    def doMoveTo(self, position):
        """ Move to a position in microsteps """
        x, y, z = position
        commandBytes = pack('<clllc', b'M', int(x), int(y), int(z), b'\r')
        self.sendCommandBytes(commandBytes)
        reply = self.readReply(size=1, format='<c')

        if reply != (b'\r',):
            raise Exception(f"Expected carriage return, but got '{reply}' instead.")

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        x, y, z = self.doGetPosition()
        if x is not None:
            self.doMoveTo((x+dx, y+dy, z+dz))
        else:
            raise Exception("Unable to read position from device")

    def doHome(self):
        commandBytes = pack('<cc', b'H', b'\r')
        self.sendCommandBytes(commandBytes)
        replyBytes = self.readReply(1, '<c')
        if replyBytes is None:
            raise Exception(f"Nothing received in respnse to {commandBytes}")
        if replyBytes != (b'\r',):
            raise Exception(f"Expected carriage return, but got {replyBytes} instead.")     
        
    def work(self):
        self.home()
        commandBytes = pack('<cc', b'Y', b'\r')
        self.sendCommandBytes(commandBytes)
        replyBytes = self.readReply(1, '<c')
        if replyBytes is None:
            raise Exception(f"Nothing received in respnse to {commandBytes}")
        if replyBytes != (b'\r',):
            raise Exception(f"Expected carriage return, but got {replyBytes} instead.")


    class DebugSerialPort(DebugPort):
        def __init__(self):
            super().__init__()
            self.xSteps = 0
            self.ySteps = 0
            self.zSteps = 0

        def processInputBuffers(self, endPointIndex):
            inputBytes = self.inputBuffers[endPointIndex]

            if inputBytes[0] == b'm'[0] or inputBytes[0] == b'M'[0]:
                x,y,z = unpack("<xlllx", inputBytes)
                self.xSteps = x
                self.ySteps = y
                self.zSteps = z
                self.writeToOutputBuffer(bytearray(b'\r'), endPointIndex)
            elif inputBytes[0] == b'h'[0] or inputBytes[0] == b'H'[0]:
                self.xSteps = 0
                self.ySteps = 0
                self.zSteps = 0
                self.writeToOutputBuffer(bytearray(b'\r'), endPointIndex)
            elif inputBytes[0] == b'c'[0] or inputBytes[0] == b'C'[0]:
                data = pack('<clllc', b'c', self.xSteps, self.ySteps, self.zSteps, b'\r')
                self.writeToOutputBuffer(data, endPointIndex)
            else:
                print("Unrecognized command (not everything is implemented): {0}".format(inputBytes))

            self.inputBuffers[endPointIndex] = bytearray()
