import env
import unittest
from threading import Thread, Lock
import struct
import usb.util as util
import subprocess
from hardwarelibrary.communication import *
from typing import NamedTuple

payloadData = b'1234'
payloadString = '1234\n'
globalLock = Lock()
threadFailed = -1

class HWLMessage(NamedTuple):
    length : int = None
    msg : str = None
    format = "{0}s"


class TestSocketPort(unittest.TestCase):
    def setUp(self):
        self.port = SocketPort(host='localhost', port=6000)
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()

    # def testSocketLocal6000(self):
    #     port = SocketPort(host='localhost', port=6000)
    #     self.assertIsNotNone(port)
    #     port.open()
    #     port.close()

    def testEchoSocket(self):
        # port = SocketPort(host='localhost', port=6000)
        # self.assertIsNotNone(port)
        # port.open()
        self.port.writeData(b'Daniel')
        actual = self.port.readData(6)
        self.assertEqual(actual, b'Daniel')

    def testHWLMsg(self):
        text = b'Daniel'
        length = len(text)
        expectedData = struct.pack('<H{0}s'.format(length), length, text)
        self.port.writeData(expectedData)

        actualData = self.port.readData(2)
        (replyLength,) = struct.unpack('<H', actualData)
        replyTextData = self.port.readData(replyLength)
        actualData += replyTextData
        self.assertEqual(actualData, expectedData)

    def testHWLStringMsg(self):
        for i in range(1000):
            self.port.open()
            expectedText = 'Daniel\n'
            self.port.writeString(expectedText)
            actualText = self.port.readString()
            self.assertEqual(actualText, expectedText)
            self.port.close()

if __name__ == '__main__':
    unittest.main()
