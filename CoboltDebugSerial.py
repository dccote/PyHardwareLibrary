import re
from CommunicationPort import *

class CoboltDebugSerial:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.power = 0.1
        self.isOn = 0
        self.requestedPower = 0
        self.autostart = 1
        self._isOpen = True

    @property
    def is_open(self):
        return self._isOpen
    
    def open(self):
        if self._isOpen:
            raise IOError("port is already open")
        else:
            self._isOpen = True

        return

    def close(self):
        self._isOpen = False

        return

    def flush(self):
        return

    def read(self, length) -> bytearray:
        data = bytearray()
        for i in range(0, length):
            if len(self.outputBuffer) > 0:
                byte = self.outputBuffer.pop(0)
                data.append(byte)
            else:
                raise CommunicationReadTimeout("Unable to read data")

        return data


    def write(self, data:bytearray) -> int :
        string = data.decode('utf-8')

        match = re.search("pa\\?", string)
        if match is not None:
            replyData = bytearray("{0:0.4f}\r\n".format(self.power), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("p\\?", string)
        if match is not None:
            replyData = bytearray("{0:0.4f}\r\n".format(self.requestedPower), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("p (\\d+\\.?\\d+)\r", string)
        if match is not None:
            self.power = float(match.groups()[0])
            replyData = bytearray("OK\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("l\\?\r", string)
        if match is not None:
            replyData = bytearray("{0}\r\n".format(self.isOn), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("l1\r", string)
        if match is not None:
            replyData = bytearray()
            if self.autostart == 1:
                replyData = bytearray("Syntax error: not allowed in autostart mode\r\n", encoding='utf-8')
            else:
                self.isOn = 1
                replyData = bytearray("OK\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("l0\r", string)
        if match is not None:
            self.isOn = 0
            replyData = bytearray("OK\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)


        match = re.search("sn\\?\r", string)
        if match is not None:
            replyData = bytearray("123456\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("@cobas 1\r", string)
        if match is not None:
            self.autostart = 1
            replyData = bytearray("OK\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("@cobas 0\r", string)
        if match is not None:
            self.autostart = 0
            replyData = bytearray("OK\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("@cobas\\?\r", string)
        if match is not None:
            replyData = bytearray("{0}\r\n".format(self.autostart), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)


        match = re.search("ilk\\?\r", string)
        if match is not None:
            replyData = bytearray("1\r\n", encoding='utf-8')
            self.outputBuffer.extend(replyData)

            return len(data)

        # Error (string already includes \n)
        replyData = bytearray("Syntax error: {0}\n".format(string), encoding='utf-8')
        self.outputBuffer.extend(replyData)

        return len(data)