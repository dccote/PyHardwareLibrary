#
# uniblitzai25device.py
#
# Allows controlling the Uniblitz AI25 Auto Iris using a custom driver.
# See "driverAI25" in the "irises" folder and "ai25-direct-control-v1-2.pdf" in the "manuals" folder.
#

from serial.tools.list_ports_common import ListPortInfo
from hardwarelibrary.irises.irisdevice import *
from hardwarelibrary.communication.communicationport import CommunicationPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.debugport import DebugPort


class UniblitzAI25Device(IrisDevice):
    classIdVendor = 0x2341  # Arduino

    def __init__(self, serialNumber: str = None):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)

        self.minStep = 54  # iris closed
        self.maxStep = 0  # iris open
        self.micronsPerStep = -440
        self.minAperture = 1500  # microns when closed
        # self.incrementMicrons = 440

        self.port: CommunicationPort = None
        self.isHomed = False
        self.lastSetStep = 0

    def __del__(self):
        self.doShutdownDevice()

    def doInitializeDevice(self):
        try:
            if 'debug' in self.serialNumber:
                self.port = self.DebugSerialPort()
                self.port.open()
            else:
                try:
                    portObject: ListPortInfo = SerialPort.matchPortObjects(self.idVendor, self.idProduct, self.serialNumber)[0]
                except:
                    raise Exception("No Uniblitz Iris connected")

                self.idVendor = portObject.vid
                self.idProduct = portObject.pid
                self.serialNumber = portObject.serial_number

                portPath = portObject.device
                self.port = SerialPort(portPath=portPath)

                if self.port is None:
                    raise Exception("Cannot allocate port " + portPath)

                self.port.open(baudRate=9600, timeout=3)

            self.port.readMatchingGroups('^(driverAI25 )?Ready\r')
            self.isHomed = False
            # self.doMoveBy(-1)
            # self.doMoveBy(1)

        except Exception as err:
            self.doShutdownDevice()
            raise PhysicalDevice.UnableToInitialize(err)

    def doShutdownDevice(self):
        if self.port and self.port.isOpen:
            self.port.close()
            self.port = None

    def sendCommand(self, command: str):
        """ Writes a command to the AI25 driver. It will initialize the device if needed. On failure, it will warn and shutdown. """
        if self.port is None or not self.port.isOpen:
            self.initializeDevice()

        self.port.flush()
        self.port.writeStringExpectMatchingString(command + '\r\n', replyPattern='^!\r')

    def doGetCurrentStep(self):
        return self.lastSetStep

    def doHome(self):
        self.sendCommand('H')
        self.lastSetStep = 0
        self.isHomed = True

    def doMoveTo(self, step: int):
        self.sendCommand('{}{:02d}'.format('M' if self.isHomed else 'G', step))
        self.lastSetStep = step
        self.isHomed = True

    def doMoveBy(self, steps: int):
        increment = -1 if steps < 0 else 1
        command = 'I' if steps < 0 else 'D'  # decrease step = [I]ncrease aperture
        for _ in range(abs(steps)):
            self.sendCommand(command)
            self.lastSetStep += increment

    class DebugSerialPort(DebugPort):
        def __init__(self):
            super().__init__()
            self.minStep = 54
            self.maxStep = 0
            self.currentStep = 0

        def open(self):
            super().open()
            self.writeToOutputBuffer(bytearray('driverAI25 Ready\r\n', 'utf-8'), 0)

        def processInputBuffers(self, endPointIndex):
            command = self.inputBuffers[endPointIndex].decode('utf-8')
            reply = '!'

            # Home
            if re.match('^H\r', command):
                self.currentStep = 0

            # Increment
            elif re.match('^I\r', command):
                self.currentStep = min(self.currentStep - 1, self.maxStep)

            # Decrement
            elif re.match('^D\r', command):
                self.currentStep = max(self.currentStep + 1, self.minStep)

            # Move
            elif match := re.match('^[MG](\\d\\d)\r', command):
                target = int(match.group(1))
                if min(self.minStep, self.maxStep) <= target <= max(self.minStep, self.maxStep):
                    self.currentStep = target
                    time.sleep(0.5)
                else:
                    reply = '?'
            else:
                reply = '?'

            self.writeToOutputBuffer(bytearray(reply + '\r\n', 'utf-8'), endPointIndex)
            self.inputBuffers[endPointIndex] = bytearray()
