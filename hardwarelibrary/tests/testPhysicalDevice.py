import env
import unittest

from hardwarelibrary.devicemanager import *
from hardwarelibrary.motion import DebugLinearMotionDevice, SutterDevice, IntellidriveDevice
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.powermeters import IntegraDevice
# from hardwarelibrary.cameras import OpenCVCamera
from hardwarelibrary.echodevice import EchoDevice, DebugEchoDevice


class DebugPhysicalDevice(PhysicalDevice):
    classIdVendor = 0xffff
    classIdProduct = 0xfffe

    def __init__(self):
        super().__init__("debug", DebugPhysicalDevice.classIdProduct, DebugPhysicalDevice.classIdVendor)
        self.errorInitialize = False
        self.errorShutdown = False

    def doInitializeDevice(self):
        if self.errorInitialize:
            raise RuntimeError()

    def doShutdownDevice(self):
        if self.errorShutdown:
            raise RuntimeError()

class BaseTestCases:
    class TestPhysicalDeviceBase(unittest.TestCase):
        def setUp(self):
            super().setUp()
            DeviceManager().updateConnectedDevices()

            self.device = None
            self.isRunning = False
            self.notificationReceived = None

            DeviceManager().destroy()
            NotificationCenter().destroy()

        def tearDown(self):
            if self.device is not None:
                self.device.shutdownDevice()
                self.device = None

            DeviceManager().removeAllDevices()
            super().tearDown()

        def testIsRunning(self):
            self.assertFalse(self.isRunning)

        def testBaseInit(self):
            self.assertTrue(len(self.device.serialNumber) > 0)
            self.assertTrue(self.device.idVendor != 0)
            self.assertTrue(self.device.idProduct != 0)

        def testInitialUnconfiguredState(self):
            self.assertTrue(self.device.state == DeviceState.Unconfigured)

        def testConfiguredStateAfterInitialize(self):
            self.assertEqual(self.device.state, DeviceState.Unconfigured)
            self.device.initializeDevice()
            self.assertEqual(self.device.state, DeviceState.Ready)

        def testConfiguredStateSequenceToShutdown(self):        
            try:
                self.assertTrue(self.device.state == DeviceState.Unconfigured)
                self.device.initializeDevice()
                self.assertTrue(self.device.state == DeviceState.Ready)
                self.device.shutdownDevice()
                self.assertTrue(self.device.state == DeviceState.Recognized)
            except Exception as error:
                self.device.shutdownDevice()
                self.assertTrue(self.device.state == DeviceState.Unrecognized)

        def testPostNotificationWillInitialize(self):
            nc = NotificationCenter()
            nc.addObserver(observer=self, method=self.handle, notificationName=PhysicalDeviceNotification.willInitializeDevice, observedObject=self.device)
            self.assertIsNone(self.notificationReceived)
            self.device.initializeDevice()
            self.assertIsNotNone(self.notificationReceived)
            self.assertEqual(self.notificationReceived.name, PhysicalDeviceNotification.willInitializeDevice)
            nc.removeObserver(self)

        def testPostNotificationDidInitialize(self):
            nc = NotificationCenter()
            nc.addObserver(observer=self, method=self.handle, notificationName=PhysicalDeviceNotification.didInitializeDevice, observedObject=self.device)
            self.assertIsNone(self.notificationReceived)
            self.device.initializeDevice()
            self.assertIsNotNone(self.notificationReceived)
            nc.removeObserver(self)

        def testPostNotificationWillShutdown(self):
            nc = NotificationCenter()
            nc.addObserver(observer=self, method=self.handle, notificationName=PhysicalDeviceNotification.willShutdownDevice, observedObject=self.device)
            self.assertIsNone(self.notificationReceived)
            self.device.initializeDevice()
            self.device.shutdownDevice()
            self.assertIsNotNone(self.notificationReceived)
            nc.removeObserver(self)

        def testPostNotificationDidShutdown(self):
            nc = NotificationCenter()
            nc.addObserver(observer=self, method=self.handle, notificationName=PhysicalDeviceNotification.didShutdownDevice, observedObject=self.device)
            self.assertIsNone(self.notificationReceived)
            self.device.initializeDevice()
            self.device.shutdownDevice()
            self.assertIsNotNone(self.notificationReceived)
            nc.removeObserver(self)

        def testPhysicalDeviceRecognizedByDeviceManager(self):
            if self.device.idVendor == 0xffff or self.device.serialNumber == 'debug':
                raise (unittest.SkipTest("Debug devices not recognized by DM"))

            classType = type(self.device)
            self.device.shutdownDevice()
            del(self.device)
            self.device = None

            dm = DeviceManager()
            dm.startMonitoring()
            time.sleep(1)

            matchedDevice = dm.matchPhysicalDevicesOfType(classType)
            self.assertTrue(len(matchedDevice) == 1)
            self.device = matchedDevice[0]
            self.device.initializeDevice()
            self.assertTrue(self.device.state == DeviceState.Ready)
            dm.stopMonitoring()

        def testPhysicalDeviceRecognizedByDeviceManagerSynchronously(self):
            if self.device.idVendor == 0xffff or self.device.serialNumber == 'debug':
                raise (unittest.SkipTest("Debug devices not recognized by DM"))

            classType = type(self.device)
            self.device.shutdownDevice()
            del(self.device)
            self.device = None

            dm = DeviceManager()
            dm.updateConnectedDevices()
            matchedDevice = dm.matchPhysicalDevicesOfType(classType)
            self.assertTrue(len(matchedDevice) == 1)
            self.device = matchedDevice[0]
            self.device.initializeDevice()
            self.assertTrue(self.device.state == DeviceState.Ready)

        def handle(self, notification):
            self.notificationReceived = notification

        def testCommandHelp(self):
            self.device.commandHelp()

class TestDebugPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = DebugPhysicalDevice()

    def testConfiguredStateSequenceToShutdownWithInitializeError(self):
        self.device.errorInitialize = True
        self.assertTrue(self.device.state == DeviceState.Unconfigured)
        with self.assertRaises(Exception):
            self.device.initializeDevice()
        self.assertTrue(self.device.state == DeviceState.Unrecognized)
        self.device.shutdownDevice()
        self.assertTrue(self.device.state == DeviceState.Unrecognized)

    def testConfiguredStateSequenceToShutdownWithShutdownError(self):
        self.device.errorShutdown = True
        self.assertTrue(self.device.state == DeviceState.Unconfigured)
        self.device.initializeDevice()
        self.assertTrue(self.device.state == DeviceState.Ready)
        with self.assertRaises(Exception):
            self.device.shutdownDevice()
        self.assertTrue(self.device.state == DeviceState.Recognized)

class TestLinearMotionPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = DebugLinearMotionDevice()

class TestSutterPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = SutterDevice(serialNumber="debug")

class TestIntellidrivePhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = IntellidriveDevice("AH06UKI3")

class TestSpectrometerPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        try:
            self.device = DeviceManager().anySpectrometerDevice()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No spectrometer connected"))

class TestPowerMeterPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        try:
            self.device = IntegraDevice()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No powermeter connected"))

class TestTektronikPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        try:
            self.device = OscilloscopeDevice()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No oscilloscope connected"))

class TestEchoPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        try:
            self.device = EchoDevice()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No ECHO connected"))

    def testEchoCommands(self):
        self.device.initializeDevice()
        for name, command in self.device.commands.items():
            try:
                self.device.sendCommand(command)
            except Exception as err:
                self.fail("Unable to send command {0} to device {1}: {2}".format(command.name, self.device, err))
        self.device.shutdownDevice()

class TestDebugEchoPhysicalDevice(TestEchoPhysicalDevice):
    def setUp(self):
        super().setUp()
        try:
            self.device = DebugEchoDevice()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No ECHO connected"))


class TestCameraPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        try:
            self.device = OpenCVCamera()
            self.assertIsNotNone(self.device)
        except Exception as err:
            raise (unittest.SkipTest("No Facetime Camera connected"))

if __name__ == '__main__':
    unittest.main()
