import time
from enum import Enum
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from threading import Thread, RLock
try:
    import cv2
except Exception as err:
    print("No support for OpenCVcameras")
    pass
    
import re

class CameraDeviceNotification(Enum):
    willStartCapture    = "willStartCapture"
    didStartCapture     = "didStartCapture"
    willStopCapture     = "willStopCapture"
    didStopCapture      = "didStopCapture"
    imageCaptured       = "imageCaptured"

class CameraDevice(PhysicalDevice):
    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.quitLoop = False
        self.lock = RLock()
        self.mainLoop = None

    def doInitializeDevice(self):
        pass # nothing to do, but incuded by symmetry with doShutdown

    def doShutdownDevice(self):
        with self.lock:
            if self.isCapturing:
                self.stop()

    def livePreview(self):
        NotificationCenter().postNotification(notificationName=CameraDeviceNotification.willStartCapture,
                                              notifyingObject=self)
        self.captureLoopSynchronous()

    def start(self):
        with self.lock:
            if not self.isCapturing:
                self.quitLoop = False
                self.mainLoop = Thread(target=self.captureLoop, name="Camera-CaptureLoop")
                NotificationCenter().postNotification(notificationName=CameraDeviceNotification.willStartCapture, notifyingObject=self)
                self.mainLoop.start()
            else:
                raise RuntimeError("Capture loop already running")

    @property
    def isCapturing(self):
        return self.mainLoop is not None

    def stop(self):
        if self.isCapturing:
            NotificationCenter().postNotification(CameraDeviceNotification.willStopCapture, notifyingObject=self)
            with self.lock:
                self.quitLoop = True
            self.mainLoop.join()
            self.mainLoop = None
            NotificationCenter().postNotification(CameraDeviceNotification.didStopCapture, notifyingObject=self)
        else:
            raise RuntimeError("No monitoring loop running")

    def captureLoopSynchronous(self):
        frame = None
        NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture,
                                              notifyingObject=self)
        while (True):
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            cv2.imshow('Preview (Q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                NotificationCenter().postNotification(CameraDeviceNotification.willStopCapture, notifyingObject=self)
                break

        cv2.destroyAllWindows()
        NotificationCenter().postNotification(CameraDeviceNotification.didStopCapture, notifyingObject=self)

    def captureFrames(self, n=1):
        frames = []
        for i in range(n):
            frames.append(self.doCaptureFrame())
        return frames

    def captureLoopThread(self):
        frame = None
        NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture,
                                              notifyingObject=self)
        while (True):
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            if self.quitLoop:
                return

class OpenCVCamera(CameraDevice):

    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.cameraHandler = None
        self.cvCameraIndex = 0
        if serialNumber is not None:
            self.cvCameraIndex = int(serialNumber)

    def openCVProperties(self):
        properties = {}
        for property in dir(cv2):
            if re.search('CAP_', property) is not None:
                indexProp = getattr(cv2, property)
                value = cam.get(indexProp)
                if value != 0:
                    properties[property] = value
        return properties

    @classmethod
    def isCompatibleWith(cls, serialNumber, idProduct, idVendor):
        return False

        try:
            cameraIndex = int(serialNumber)
        except Exception as err:
            cameraIndex = 0

        cam = cv2.VideoCapture(cameraIndex)
        wasAcquired, frame = cam.read()
        cam.release()

        return wasAcquired

    def doInitializeDevice(self):
        super().doInitializeDevice()
        with self.lock:
            # FIXME: Open the first camera we find
            self.cameraHandler = cv2.VideoCapture(self.cvCameraIndex)

            if self.cameraHandler is None:
                raise Exception("Could not open video device")

            if not (self.cameraHandler.isOpened()):
                raise Exception("Could not open video device")

    def doShutdownDevice(self):
        super().doShutdownDevice()
        with self.lock:
            self.cameraHandler.release()
            self.cameraHandler = None

    def doCaptureFrame(self):
        with self.lock:
            # Capture frame-by-frame
            ret, frame = self.cameraHandler.read()
            return frame

    @classmethod
    def availableCameras(cls):
        return 0

        numberOfCameras = 0
        for i in range(10):
            cam = cv2.VideoCapture(i)
            wasAcquired, frame = cam.read()
            cam.release()

            if not wasAcquired:
                break

            numberOfCameras += 1

        return numberOfCameras

if __name__ == "__main__":
    print(OpenCVCamera.availableCameras())
    cam = OpenCVCamera()
    cam.initializeDevice()
    cam.livePreview()
    cam.shutdownDevice()
