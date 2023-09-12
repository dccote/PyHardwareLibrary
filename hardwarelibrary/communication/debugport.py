import time
import random

from hardwarelibrary.communication import *
from threading import Thread, Lock

class DebugDataCommand(Command):
    def __init__(self, name, dataHexRegex = None, unpackingMask = None, endPoints = (None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.data : bytearray = data
        self.dataHexRegex: str = dataHexRegex
        self.unpackingMask:str = unpackingMask

    def send(self, port) -> bool:
        try:
            self.isSent = True
            nBytes = port.writeData(data=self.data, endPoint=self.endPoints[0])
            if self.replyDataLength > 0:
                self.reply = port.readData(length=self.replyDataLength)
            elif self.replyHexRegex is not None:
                raise NotImplementedError("DataCommand reply pattern not implemented")
                # self.reply = port.readData(length=self.replyDataLength)
            self.isSentSuccessfully = True
        except Exception as err:
            
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            raise(err)

        return False

class DebugPort(CommunicationPort):
    def __init__(self, delay=0):
        self.inputBuffers = [bytearray()]
        self.outputBuffers = [bytearray()]
        self.delay = delay
        self._isOpen = False
        super(DebugPort, self).__init__()

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

    def bytesAvailable(self, endPoint=0):
        return len(self.outputBuffers[endPoint])

    def flush(self):
        self.inputBuffers = [bytearray()]
        self.outputBuffers = [bytearray()]

    def readData(self, length, endPoint=None):
        if endPoint is None:
            endPoint = 0

        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.outputBuffers[endPoint]) > 0:
                    byte = self.outputBuffers[endPoint].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data, endPoint=None):
        if endPoint is None:
            endPoint = 0

        with self.portLock:
            self.inputBuffers[endPoint].extend(data)

        self.processInputBuffers(endPoint)

        return len(data)

    def writeToOutputBuffer(self, data, endPointIndex):
        self.outputBuffers[endPointIndex].extend(data)

    def processInputBuffers(self, endPointIndex):
        # We default to ECHO for simplicity

        inputBytes = self.inputBuffers[endPointIndex]

        # Do something, here we do an Echo
        self.writeToOutputBuffer(inputBytes, endPointIndex)
        self.inputBuffers[endPointIndex] = bytearray()