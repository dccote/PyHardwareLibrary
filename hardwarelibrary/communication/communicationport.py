import serial
import re
import time
import random
import inspect
from threading import RLock
from .commands import *

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
        self.terminator = b'\n'

    @property
    def isOpen(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    @property
    def isNotOpen(self):
        return not self.isOpen

    def open(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def close(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def bytesAvailable(self) -> int:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def flush(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def readData(self, length, endPoint=None) -> bytearray:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def writeData(self, data, endPoint=None) -> int:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def readString(self, endPoint=None) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            try:
                while (byte != b''):
                    byte = self.readData(1, endPoint)
                    data += byte
                    if byte == self.terminator:
                        break
            except CommunicationReadTimeout as err:
                raise CommunicationReadTimeout("Only obtained {0}".format(data))

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endPoint=None) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endPoint)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
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

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            reply, groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern, endPoints)
            if len(groups) >= 1:
                return reply, groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])

            match = re.search(replyPattern, reply)

            if match is not None:
                return reply, match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))

    def readMatchingGroups(self, replyPattern, alternatePattern = None, endPoint=None):
        reply = self.readString(endPoint=endPoint)

        match = re.search(replyPattern, reply)

        if match is not None:
            return reply, match.groups()
        else:
            raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))

