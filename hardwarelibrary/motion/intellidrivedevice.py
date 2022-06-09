from hardwarelibrary.motion.rotationdevice import *
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import DebugPort

import time
from struct import *

class State(Enum):
    notInit = 0,
    init = 1,
    unknown = 2,
    referenced = 3,
    configuration = 4,
    homing = 5,
    moving = 6,
    ready = 7,
    disable = 8,
    jogging = 9


class IntellidriveDevice(RotationDevice):
    classIdVendor = 0x0403
    classIdProduct = 0x6001 

    def __init__(self, serialNumber):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self._steps = None
        self.internalState = State.notInit
        self.stepsPerDegree = 138.888*6 # I don't know where I got this number from. The *6 is a quick fix.
        self.hasEncoder = False

    def doInitializeDevice(self):
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor, idProduct=self.idProduct, serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Intellidrive Device connected")

                self.port = SerialPort(portPath=portPath)
                self.port.open(baudRate=9600)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port {0}".format(portPath))

            self.doGetSatus()

            self.port.writeStringExpectMatchingString("s r0x24 31\r", replyPattern="ok\r")
            self.port.writeStringExpectMatchingString("s r0xc2 514\r", replyPattern="ok\r")

            if not self.hasEncoder:
                self.doHome() # We need to know where we are if we don't have an encoder

            self.internalState = State.ready

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            self.internalState = State.notInit
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def doGetSatus(self):
        reply, statusStr = self.port.writeStringReadFirstMatchingGroup('g r0xc9\n', replyPattern=r'v\s(-?\d+)')
        return int(statusStr)

    def isMoving(self):
        status = self.doGetSatus()
        return status & (1 << 15) != 0

    def isHoming(self):
        status = self.doGetSatus()
        return status & (1 << 13) != 0

    def isReferenced(self):
        status = self.doGetSatus()
        return status & (1 << 12) != 0

    def doGetOrientation(self) -> float:
        if self.hasEncoder:
            reply, steps = self.port.writeStringReadFirstMatchingGroup('g r0x32\r', replyPattern=r'v\s(\d+)')
            self._steps = steps

        return self._steps / self.stepsPerDegree

    def doMoveTo(self, angle):
        self.port.writeStringExpectMatchingString('s r0xc8 0\r', replyPattern='ok')
        self.port.writeStringExpectMatchingString('s r0x24 31\r', replyPattern='ok')

        steps = int(angle * self.stepsPerDegree)

        self.port.writeStringExpectMatchingString("s r0xca {0:d}\r".format(steps), replyPattern='ok')
        self.port.writeStringExpectMatchingString('t 1\r', replyPattern='ok')

        while self.isMoving():
            time.sleep(0.05)

        self._steps = steps

    def doMoveBy(self, displacement):
        raise NotImplementedError()


    def doHome(self):
        self.port.writeStringExpectMatchingString('t 2\n', replyPattern='ok')

        while self.isHoming():
            time.sleep(0.05)

        self._steps = 0

        if not self.isReferenced():
            raise Exception("Homing failed")
