#
# irisdevice.py
#

from enum import Enum
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification


class IrisNotification(Enum):
    willMove = "willMove"
    didMove = "didMove"
    didGetPosition = "didGetPosition"


class IrisDevice(PhysicalDevice):
    def __init__(self, serialNumber: str, idProduct: int, idVendor: int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.minStep = 0  # closed
        self.maxStep = 2**31  # open
        self.micronsPerStep = 1000
        self.minAperture = -1  # microns when closed

    def convertMicronsToStep(self, microns: float) -> int:
        """ Converts an aperture size in microns to a native step position. """
        if self.micronsPerStep == 0:
            raise ValueError("micronsPerStep == 0")
        if self.minAperture < 0:
            raise ValueError("minAperture < 0")

        return round((microns - self.minAperture) / self.micronsPerStep + self.minStep)

    def convertStepToMicrons(self, step: int) -> float:
        """ Converts a native step position to an aperture size in microns. """
        if self.minAperture < 0:
            raise ValueError("minAperture < 0")

        return (step - self.minStep) * self.micronsPerStep + self.minAperture

    def currentStep(self) -> int:
        """ Returns the current native position. """
        step = self.doGetCurrentStep()
        NotificationCenter().postNotification(IrisNotification.didGetPosition, notifyingObject=self, userInfo=step)
        return step

    def aperture(self) -> float:
        """ Returns the current aperture size in microns. """
        return self.convertStepToMicrons(self.currentStep())

    def home(self):
        NotificationCenter().postNotification(IrisNotification.willMove, notifyingObject=self)
        self.doHome()
        NotificationCenter().postNotification(IrisNotification.didMove, notifyingObject=self)

    def moveTo(self, step: int):
        NotificationCenter().postNotification(IrisNotification.willMove, notifyingObject=self, userInfo=step)
        self.doMoveTo(step)
        NotificationCenter().postNotification(IrisNotification.didMove, notifyingObject=self, userInfo=step)

    def moveToMicrons(self, microns):
        self.moveTo(self.convertMicronsToStep(microns))

    def moveBy(self, steps: int):
        NotificationCenter().postNotification(IrisNotification.willMove, notifyingObject=self, userInfo=steps)
        self.doMoveBy(steps)
        NotificationCenter().postNotification(IrisNotification.didMove, notifyingObject=self, userInfo=steps)

    def moveByMicrons(self, microns):
        self.moveBy(round(microns / self.micronsPerStep))

    def isValidStep(self, step: int) -> bool:
        return min(self.minStep, self.maxStep) < step < max(self.minStep, self.maxStep)

    def isValidAperture(self, microns: float) -> bool:
        return self.isValidStep(self.convertMicronsToStep(microns))

    def doGetCurrentStep(self) -> int:
        raise NotImplementedError

    def doHome(self):
        raise NotImplementedError

    def doMoveTo(self, step):
        raise NotImplementedError

    def doMoveBy(self, steps):
        raise NotImplementedError


class DebugIrisDevice(IrisDevice):
    classIdProduct = 0xFFFD
    classIdVendor = debugClassIdVendor

    def __init__(self):
        super().__init__("debug", DebugIrisDevice.classIdProduct, DebugIrisDevice.classIdVendor)
        self.minStep = 0  # iris closed
        self.maxStep = 100  # iris open
        self.micronsPerStep = 100
        self.minAperture = 0  # microns when closed
        self.lastSetStep = 0

    def doHome(self):
        self.lastSetStep = 0

    def doGetCurrentStep(self):
        return self.lastSetStep

    def doMoveTo(self, step):
        self.lastSetStep = step

    def doMoveBy(self, steps):
        self.lastSetStep += steps

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass
