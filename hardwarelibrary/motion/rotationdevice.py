from enum import Enum
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class RotationMotionNotification(Enum):
    willMove       = "willMove"
    didMove        = "didMove"
    didGetOrientation = "didGetOrientation"

class Direction(Enum):
    unidirectional = "unidirectional"
    bidirectional  = "bidirectional"

class RotationDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.theta = None

    def moveTo(self, angle):
        NotificationCenter().postNotification(RotationMotionNotification.willMove, notifyingObject=self, userInfo=angle)
        self.doMoveTo(angle)
        NotificationCenter().postNotification(RotationMotionNotification.didMove, notifyingObject=self, userInfo=angle)

    def moveBy(self, deltaTheta):
        NotificationCenter().postNotification(RotationMotionNotification.willMove, notifyingObject=self, userInfo=deltaTheta)
        self.doMoveBy(deltaTheta)
        NotificationCenter().postNotification(RotationMotionNotification.didMove, notifyingObject=self, userInfo=deltaTheta)

    def orientation(self) -> ():
        orientation = self.doGetOrientation()
        NotificationCenter().postNotification(RotationMotionNotification.didGetOrientation, notifyingObject=self, userInfo=orientation)
        return orientation

    def home(self) -> ():
        NotificationCenter().postNotification(RotationMotionNotification.willMove, notifyingObject=self)
        self.doHome()
        NotificationCenter().postNotification(RotationMotionNotification.didMove, notifyingObject=self)


class DebugRotationDevice(RotationDevice):
    classIdProduct = 0xfffd
    classIdVendor = 0xffff
    def __init__(self):
        super().__init__("debug", DebugLinearMotionDevice.classIdProduct, DebugLinearMotionDevice.classIdVendor )
        self.orientation = None

        self._debugOrientation = 0

    def doGetOrientation(self) -> float:
        return self._debugOrientation

    def doMoveTo(self, angle):
        self._debugOrientation = angle

    def doMoveBy(self, displacement):
        self._debugOrientation += angle

    def doHome(self):
        self._debugOrientation = 0

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass