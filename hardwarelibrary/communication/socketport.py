from hardwarelibrary.communication import *
import time
import socket

class SocketPort(CommunicationPort):
    """

    """
    def __init__(self, host=None, port=6000):
        CommunicationPort.__init__(self)
        self.host = host
        self.port = port
        self.sock = None

    def open(self):
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def readData(self, length, endPoint=0) -> bytearray:
        chunks = []
        bytes_recd = 0
        while bytes_recd < length:
            chunk = self.sock.recv(min(length - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("socket connection broken on read")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return b''.join(chunks)

    def writeData(self, data, endPoint=0) -> int:
        MSGLEN = len(data)
        totalsent = 0
        while totalsent < MSGLEN:
            sent = self.sock.send(data[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken on write")
            totalsent = totalsent + sent
        return totalsent

