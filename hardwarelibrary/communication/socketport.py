import socket, os
from .communicationport import *
import time
import re

class SocketPort(CommunicationPort):
    def __init__(self, address, portNumber):
        CommunicationPort.__init__(self)
        self.address = address
        self.portNumber = portNumber


class SocketServerPort(CommunicationPort):
    """
    An implementation of CommunicationPort using sockets (i.e. internet connections)
    """

    def __init__(self, address, portNumber):
        CommunicationPort.__init__(self)
        self.address = address
        self.portNumber = portNumber

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.address, self.portNumber))
        self.sock.listen(5)
        try:
            while not self.quitServer:
                connection, address = self.sock.accept()

                while True:
                    c = None
                    bytes = bytearray()
                    while c != b'\n':
                        c = connection.recv(1)
                        bytes.extend(c)

                    commandName = bytes.decode("utf-8")
                    command = self.sendCommand(commandName)
                    print("Received request {0}".format(commandName))

                    if command is not None:
                        print("Reply received {0}".format(command.reply))
                        connection.send(b"device replied: {0}".format(command.reply))

        except Exception as err:
            with self.lock:
                if self.serverConnection is not None:
                    self.serverConnection.close()
                    self.sock.close()
