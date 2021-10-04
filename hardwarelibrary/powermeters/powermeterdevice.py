from enum import Enum
from hardwarelibrary.communication import USBPort, TextCommand
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class PowerMeterNotification(Enum):
    didMeasure     = "didMeasure"

class PowerMeterDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.absolutePower = 0
        self.calibrationWavelength = None

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power

    def getCalibrationWavelength(self):
        self.doGetCalibrationWavelength()
        return self.calibrationWavelength

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power


class IntegraDevice(PowerMeterDevice):
    classIdProduct = 0x0300
    classIdVendor = 0x1ad5

    def __init__(self, serialNumber:str = None, idProduct:int = 0x0300, idVendor:int = 0x1ad5):
        super().__init__(serialNumber, idProduct, idVendor)
        self.port = None
        self.commands = {
         "GETPOWER":TextCommand(name="GETPOWER", text="*CVU", replyPattern = r"(.+?)\r\n"),
         "VERSION":TextCommand(name="VERSION", text="*VER", replyPattern = r"(.+?)\r\n"),
         "STATUS":TextCommand(name="STATUS", text="*STS", replyPattern = r"(.+?)\r\n", finalReplyPattern=":100000000"),
         "GETWAVELENGTH":TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")
        }

        self.version = ""

    def doInitializeDevice(self):
        self.port = USBPort(idVendor=self.idVendor, idProduct=self.idProduct, interfaceNumber=0, defaultEndPoints=(1, 2))
        self.port.open()
        self.doGetVersion()

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def doGetAbsolutePower(self):
        getPowerCommand = self.commands["GETPOWER"]
        getPowerCommand.send(port=self.port)
        self.absolutePower = getPowerCommand.matchAsFloat(0)

    def doGetCalibrationWavelength(self):
        getWavelength = self.commands["GETWAVELENGTH"]
        getWavelength.send(port=self.port)
        self.calibrationWavelength = getWavelength.matchAsFloat(0)

    def doGetVersion(self):
        getVersion = self.commands["VERSION"]
        getVersion.send(port=self.port)
        self.version = getVersion.matchGroups[0]
