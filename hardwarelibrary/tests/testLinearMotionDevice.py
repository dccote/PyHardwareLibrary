import env
import unittest

from hardwarelibrary.motion.linearmotiondevice import *
from hardwarelibrary.motion.sutterdevice import SutterDevice
from hardwarelibrary.notificationcenter import NotificationCenter


class BaseTestCases:
    class TestLinearMotionDevice(unittest.TestCase):
        device: LinearMotionDevice

        def setUp(self):
            # Set self.device in subclass
            self.willNotificationReceived = False
            self.didNotificationReceived = False
            if self.device is None:
                raise (unittest.SkipTest("No device defined in subclass of BaseTestCase"))

            try:
                self.device.initializeDevice()
            except Exception as err:
                raise (unittest.SkipTest("No devices connected"))

        def tearDown(self):
            self.device.shutdownDevice()

        def testDevicePosition(self):
            (x, y, z) = self.device.position()
            self.assertIsNotNone(x)
            self.assertIsNotNone(y)
            self.assertIsNotNone(z)
            self.assertTrue(x >= 0)
            self.assertTrue(y >= 0)
            self.assertTrue(z >= 0)

        def testPosition(self):
            (x, y, z) = self.device.position()
            self.assertIsNotNone(x)
            self.assertIsNotNone(y)
            self.assertIsNotNone(z)
            self.assertTrue(x >= 0)
            self.assertTrue(y >= 0)
            self.assertTrue(z >= 0)

        def testDeviceMove(self):
            destination = (4000, 5000, 6000)
            self.device.moveTo(destination)

            (x,y,z) = self.device.position()
            self.assertTrue(x == destination[0])
            self.assertTrue(y == destination[1])
            self.assertTrue(z == destination[2])

        def testDeviceMoveBy(self):
            (xo, yo, zo) = self.device.position()

            self.device.moveBy((-1000, -2000, -3000))

            (x, y, z) = self.device.position()
            self.assertEqual(x-xo , -1000)
            self.assertEqual(y-yo , -2000)
            self.assertEqual(z-zo , -3000)


        def testPositionInMicrons(self):
            (x, y, z) = self.device.positionInMicrons()
            self.assertIsNotNone(x)
            self.assertIsNotNone(y)
            self.assertIsNotNone(z)
            self.assertTrue(x >= 0)
            self.assertTrue(y >= 0)
            self.assertTrue(z >= 0)

        def testDeviceMoveInMicrons(self):
            destination = (4000, 5000, 6000)
            self.device.moveInMicronsTo(destination)

            (x,y,z) = self.device.positionInMicrons()
            self.assertEqual(x, destination[0])
            self.assertEqual(y, destination[1])
            self.assertEqual(z, destination[2])

        def testDeviceMoveByInMicrons(self):
            (xo, yo, zo) = self.device.positionInMicrons()

            self.device.moveInMicronsBy((-1000, -2000, -3000))

            (x, y, z) = self.device.positionInMicrons()
            self.assertEqual(x-xo, -1000)
            self.assertEqual(y-yo, -2000)
            self.assertEqual(z-zo, -3000)

        def testDeviceHome(self):
            self.device.home()
            (x, y, z) = self.device.position()
            self.assertEqual(x, 0)
            self.assertEqual(y, 0)
            self.assertEqual(z, 0)

        def handleWill(self, notification):
            self.willNotificationReceived = True

        def handleDid(self, notification):
            self.didNotificationReceived = True

        def testPositionNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=LinearMotionNotification.didGetPosition)
            (x, y, z) = self.device.position()
            self.assertTrue(self.didNotificationReceived)
            NotificationCenter().removeObserver(self)

        def testDeviceMoveNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=LinearMotionNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=LinearMotionNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            destination = (4000, 5000, 6000)
            self.device.moveTo(destination)

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)

        def testDeviceMoveByNotifications(self):
            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=LinearMotionNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=LinearMotionNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            self.device.moveBy((-1000, -2000, -3000))

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)

        def testDeviceHomeNotifications(self):

            NotificationCenter().addObserver(self, method=self.handleWill, notificationName=LinearMotionNotification.willMove)
            NotificationCenter().addObserver(self, method=self.handleDid, notificationName=LinearMotionNotification.didMove)

            self.assertFalse(self.willNotificationReceived)
            self.assertFalse(self.didNotificationReceived)

            self.device.home()

            self.assertTrue(self.willNotificationReceived)
            self.assertTrue(self.didNotificationReceived)

            NotificationCenter().removeObserver(self)


class TestDebugLinearMotionDeviceBase(BaseTestCases.TestLinearMotionDevice):
    def setUp(self):
        self.device = DebugLinearMotionDevice()
        super().setUp()


class TestDebugSutterDeviceBase(BaseTestCases.TestLinearMotionDevice):
    def setUp(self):
        self.device = SutterDevice("debug")
        super().setUp()


class TestRealSutterDeviceBase(BaseTestCases.TestLinearMotionDevice):
    def setUp(self):
        self.device = SutterDevice()
        super().setUp()


if __name__ == '__main__':
    unittest.main()
