import env
import unittest

from hardwarelibrary.irises.irisdevice import *
from hardwarelibrary.irises.uniblitzai25device import UniblitzAI25Device
from hardwarelibrary.notificationcenter import NotificationCenter


class BaseTestCases:
    class TestIrisDevice(unittest.TestCase):
        device: IrisDevice

        def setUp(self):
            # Set self.device in subclass
            self.willNotificationReceived = False
            self.didNotificationReceived = False
            if self.device is None:
                raise (unittest.SkipTest("No device defined in subclass of BaseTestCase"))

            try:
                self.device.initializeDevice()
            except:
                raise unittest.SkipTest("No devices connected")

        def tearDown(self):
            self.device.shutdownDevice()

        def testCurrentStep(self):
            step = self.device.currentStep()
            self.assertIsNotNone(step)
            self.assertTrue(step >= 0)

        def testAperture(self):
            aperture = self.device.aperture()
            self.assertIsNotNone(aperture)
            self.assertTrue(aperture >= 0)

        def testMove(self):
            target = self.device.minStep + (self.device.maxStep - self.device.minStep) // 3
            self.device.moveTo(target)
            self.assertEqual(self.device.currentStep(), target)

        def testMoveBy(self):
            step = self.device.currentStep()
            target = 2
            self.device.moveBy(target)
            self.assertEqual(self.device.currentStep(), step + target)

        def testMoveToMicrons(self):
            target = self.device.minAperture + self.device.micronsPerStep * ((self.device.maxStep - self.device.minStep) // 2)
            self.device.moveToMicrons(target)
            self.assertEqual(self.device.aperture(), target)

        def testMoveByMicrons(self):
            aperture = self.device.aperture()
            target = aperture + self.device.micronsPerStep * 2
            self.device.moveToMicrons(target)
            self.assertEqual(self.device.aperture(), target)

        def testDeviceHome(self):
            self.device.home()
            self.assertEqual(self.device.currentStep(), 0)

        def handleWill(self, notification):
            self.willNotificationReceived = True

        def handleDid(self, notification):
            self.didNotificationReceived = True

        def testPositionNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=IrisNotification.didGetPosition)
            self.device.currentStep()
            self.assertTrue(self.didNotificationReceived)
            NotificationCenter().removeObserver(self)

        def testDeviceMoveNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=IrisNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=IrisNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            self.device.moveTo(self.device.minStep + (self.device.maxStep - self.device.minStep) // 2)

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)

        def testDeviceMoveByNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=IrisNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=IrisNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            self.device.moveBy(2)

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)

        def testDeviceHomeNotifications(self):

            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=IrisNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=IrisNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            self.device.home()

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)


class TestDebugLinearMotionDeviceBase(BaseTestCases.TestIrisDevice):
    def setUp(self):
        self.device = DebugIrisDevice()
        super().setUp()


class TestDebugUniblitzAI25DeviceBase(BaseTestCases.TestIrisDevice):
    def setUp(self):
        self.device = UniblitzAI25Device("debug")
        super().setUp()


class TestRealUniblitzAI25DeviceBase(BaseTestCases.TestIrisDevice):
    def setUp(self):
        self.device = UniblitzAI25Device()
        super().setUp()


if __name__ == '__main__':
    unittest.main()
