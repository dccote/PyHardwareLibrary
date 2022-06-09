
import env
import unittest

from hardwarelibrary.communication.serialport import *
from hardwarelibrary.motion.intellidrivedevice import IntellidriveDevice

serialNumber = "A103LLZD"

class TestIntellidriveBasicCommandsWithPySerial(unittest.TestCase):
    def setUp(self):
        self.port = None
        self.portPath = None
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == 0x0403 and port.pid == 0x6001: # Sutter Instruments
                self.portPath = "/dev/cu.usbserial-{0}".format(serialNumber)

        if self.portPath is None:
            raise(unittest.SkipTest("No Intellidrive connected. Skipping."))

    def tearDown(self):
        if self.port is not None:
            self.port.close()

    def testPySerialPortNotNone(self):
        self.assertIsNotNone(self.portPath)
        self.assertIsNotNone(serial.Serial(self.portPath))

    def testPySerialPortWrite(self):
        self.port = serial.Serial(self.portPath, timeout=2)
        self.assertIsNotNone(self.port)
        self.port.write(b's r0x24 31\n')
        reply = self.port.read_until(expected='\r')
        self.assertEqual(reply, b'ok\r')
        self.port.close()

    def testPySerialPortHome(self):
        self.port = serial.Serial(self.portPath, timeout=1)
        self.assertIsNotNone(self.port)

        self.port.write(b's r0x24 31\n')
        reply = self.port.read_until(expected='\r')
        self.assertEqual(reply, b'ok\r')

        self.port.write(b's r0xc2 514\n')
        reply = self.port.read_until(expected='\r')
        self.assertEqual(reply, b'ok\r')

        self.port.write(b't 2\n')
        reply = self.port.read_until(expected='\r')
        self.assertEqual(reply, b'ok\r')

        self.port.write(b'g r0xc9\n')
        reply = self.port.read_until(expected='\r')
        match = re.search(r"v\s(-?\d+)", reply.decode())
        self.assertIsNotNone(match)
        status = int(match.group(1))
        print(status)
        # self.assertFalse( status & (1 << 14) )
        self.port.close()



class TestIntellidriveDeviceWithSerialPort(unittest.TestCase):

    def testPort(self):
        port = SerialPort.matchPorts(serialNumber=serialNumber, idVendor=0x0403, idProduct = 0x6001)
        self.assertIsNotNone(port)

    def testOpenPort(self):
        ports = SerialPort.matchPorts(serialNumber=serialNumber, idVendor=0x0403, idProduct = 0x6001)
        port = SerialPort(portPath=ports[0])
        port.open(baudRate=9600)
        self.assertIsNotNone(port)
        port.close()

    def testWritePort(self):
        ports = SerialPort.matchPorts(serialNumber=serialNumber, idVendor=0x0403, idProduct = 0x6001)
        port = SerialPort(portPath=ports[0])
        port.open(baudRate=9600)
        port.terminator = b'\r'
        port.writeString("s r0x24 31\n")
        reply = port.readString()
        self.assertEqual('ok\r', reply)
        port.close()

    def testHome(self):
        ports = SerialPort.matchPorts(serialNumber=serialNumber, idVendor=0x0403, idProduct = 0x6001)
        port = SerialPort(portPath=ports[0])
        port.open(baudRate=9600)
        port.terminator = b'\r'

        port.writeStringExpectMatchingString('s r0x24 31\n', replyPattern='ok')

        port.writeString('s r0xc2 514\n')
        reply = port.readString()
        self.assertEqual(reply, 'ok\r')

        port.writeString('t 2\n')
        reply = port.readString()
        self.assertEqual(reply, 'ok\r')

        port.writeString('g r0xc9\n')
        reply = port.readString()
        match = re.search(r"v\s(-?\d+)", reply)
        self.assertIsNotNone(match)
        status = int(match.group(1))
        print("{0:x}".format(status))
        # self.assertFalse( status & (1 << 14) )
        port.close()

    def testHomeWithCommands(self):
        ports = SerialPort.matchPorts(serialNumber="A103LLZD", idVendor=0x0403, idProduct = 0x6001)
        port = SerialPort(portPath=ports[0])
        port.open(baudRate=9600)
        port.terminator = b'\r'

        port.writeStringExpectMatchingString('s r0x24 31\n', replyPattern='ok')
        port.writeStringExpectMatchingString('s r0xc2 514\n', replyPattern='ok')
        port.writeStringExpectMatchingString('t 2\n', replyPattern='ok')
        reply, statusStr = port.writeStringReadxFirstMatchingGroup('g r0xc9\n', replyPattern=r'v\s(-?\d+)')

        status = int(statusStr)
        self.assertFalse( status & (1 << 14) )
        port.close()

class TestIntellidrivePhysicalDevice(unittest.TestCase):
    def testDeviceCreate(self):
        self.assertIsNotNone(IntellidriveDevice(serialNumber="AH06UKI3"))

    def testDeviceInitialize(self):
        dev = IntellidriveDevice(serialNumber=serialNumber)
        self.assertIsNotNone(dev)
        dev.initializeDevice()
        dev.shutdownDevice()

    def testDeviceHome(self):
        dev = IntellidriveDevice(serialNumber=serialNumber)
        self.assertIsNotNone(dev)
        dev.initializeDevice()
        dev.doHome()
        dev.shutdownDevice()

    def testDeviceMove(self):
        dev = IntellidriveDevice(serialNumber=serialNumber)
        self.assertIsNotNone(dev)
        dev.initializeDevice()
        dev.doMoveTo(1000)
        dev.shutdownDevice()

    def testOrientation(self):
        dev = IntellidriveDevice(serialNumber=serialNumber)
        self.assertIsNotNone(dev)
        dev.initializeDevice()
        print(dev.orientation())
        dev.shutdownDevice()

    def testSpinAround(self):
        dev = IntellidriveDevice(serialNumber=serialNumber)
        self.assertIsNotNone(dev)
        dev.initializeDevice()

        for angle in [0, 180, 360, 720]:
            dev.moveTo(angle)
            actualOrientation = dev.orientation()
            self.assertAlmostEqual(angle, actualOrientation, 2)

        dev.shutdownDevice()


if __name__ == '__main__':
    unittest.main()
