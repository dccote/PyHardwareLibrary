import serial
import re
import time
import random
from threading import Thread, RLock

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class CommunicationReadAlternateMatch(Exception):
    pass

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.

    """
    
    def __init__(self):
        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        raise NotImplementedError()

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def bytesAvailable(self) -> int:
        raise NotImplementedError()

    def flush(self):
        raise NotImplementedError()

    def readData(self, length, endpoint=0) -> bytearray:
        raise NotImplementedError()

    def writeData(self, data, endpoint=0) -> int:
        raise NotImplementedError()

    def readString(self, endpoint=0) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1, endpoint)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endpoint=0) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endpoint)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])
            match = re.search(replyPattern, reply)
            if match is None:
                if alternatePattern is not None:
                    match = re.search(alternatePattern, reply)
                    if match is None:
                        raise CommunicationReadAlternateMatch(reply)
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern, endPoints)
            if len(groups) >= 1:
                return groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])

            match = re.search(replyPattern, reply)

            if match is not None:
                return match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))


class DebugEchoCommunicationPort(CommunicationPort):
    def __init__(self, delay=0):
        self.buffer = bytearray()
        self.delay = delay
        self._isOpen = False
        super(DebugEchoCommunicationPort, self).__init__()

    @property
    def isOpen(self):
        return self._isOpen    

    def open(self):
        if self._isOpen:
            raise Exception()

        self._isOpen = True
        return

    def close(self):
        self._isOpen = False
        return

    def bytesAvailable(self):
        return len(self.buffer)

    def flush(self):
        self.buffer = bytearray()

    def readData(self, length):
        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data):
        with self.portLock:
            self.buffer.extend(data)

        return len(data)

class SerialPort(CommunicationPort):
    """
    An implementation of CommunicationPort using BSD-style serial port
    
    Two strategies to initialize the SerialPort:
    1. with a bsdPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of pyserial.Serial() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    """
    def __init__(self, bsdPath=None, portPath=None, port = None):
        CommunicationPort.__init__(self, )
        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        if port is not None and port.is_open:
            port.close()
        self.port = port # direct port, must be closed.

        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        if self.port is None:
            return False    
        else:
            return self.port.is_open    

    def open(self):
        if self.port is None:
            self.port = serial.Serial(self.portPath, 19200, timeout=0.3)
        else:
            self.port.open()

    def close(self):
        self.port.close()

    def bytesAvailable(self) -> int:
        return self.port.in_waiting

    def flush(self):
        if self.isOpen:
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()

    def readData(self, length, endpoint=0) -> bytearray:
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        return data

    def writeData(self, data, endpoint=0) -> int:
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten