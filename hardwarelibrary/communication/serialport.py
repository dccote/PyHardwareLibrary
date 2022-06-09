from .communicationport import *
import time
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
import re
import pyftdi.serialext
import pyftdi.ftdi 
from pyftdi.ftdi import Ftdi
from io import StringIO

class UnableToOpenSerialPort(serial.SerialException):
    pass

class MoreThanOneMatch(serial.SerialException):
    pass

class SerialPort(CommunicationPort):
    """
    An implementation of CommunicationPort using BSD-style serial port
    
    Two strategies to initialize the SerialPort:
    1. with a portPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of pyserial.Serial() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    3. with a URL for support through pyftdi to access the chip directly. Use portPath 'ftdi://ftdi:2232h/2'
       or the find_url.py script from the distribution. More info: https://eblot.github.io/pyftdi/api/usbtools.html
       You have to add any custom VID/PID when using tools (but they are added here in SerialPort) @line 30.
    """
    def __init__(self, idVendor=None, idProduct=None, serialNumber=None, portPath=None, port=None):
        CommunicationPort.__init__(self)

        try:
            Ftdi.add_custom_product(vid=4930, pid=1, pidname="Sutter")
        except:
            pass

        if idVendor is not None and portPath is None:
            portPath = SerialPort.matchAnyPort(idVendor, idProduct, serialNumber)

        if portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        if port is not None and port.is_open:
            port.close()

        self.port = None # direct port, must be closed.

    @classmethod
    def matchSinglePort(cls, idVendor=None, idProduct=None, serialNumber=None):
        ports = cls.matchPorts(idVendor, idProduct, serialNumber)
        if len(ports) == 1:
            return ports[0]
        return None

    @classmethod
    def matchAnyPort(cls, idVendor=None, idProduct=None, serialNumber=None):
        ports = cls.matchPorts(idVendor, idProduct, serialNumber)
        if len(ports) >= 1:
            return ports[0]
        return None

    @classmethod
    def matchPorts(cls, idVendor=None, idProduct=None, serialNumber=None):
        # We must provide idVendor, idProduct and serialNumber
        # or              idVendor and idProduct
        # or              idVendor

        # We must add custom vendors when required
        try:
            if idVendor is not None and idProduct is not None:
                # print("Adding custom product")
                pyftdi.ftdi.Ftdi.add_custom_product(vid=idVendor, pid=idProduct, pidname='VID {0}: PID {1}'.format(idVendor, idProduct))
            elif idVendor is not None:
                # print("Adding custom vendor")
                pyftdi.ftdi.Ftdi.add_custom_vendor(vid=idVendor, vidname='VID {0}'.format(idVendor))

        except ValueError as err:
            # It is not an error: it is already registered
            pass


        # It sometimes happens on macOS that the ports are "doubled" because two user-space DriverExtension 
        # prepare a port (FTDI and Apple's for instance).  If that is the case, then we try to remove duplicates

        portObjects = []
        allPorts = comports()            # From PySerial
        ftdiPorts = cls.ftdiPorts()
        # print(ftdiPorts)
        allPorts.extend(ftdiPorts) # From pyftdi

        for port in allPorts:
            if idProduct is None:
                if port.vid == idVendor:
                    portObjects.append(port)
            elif serialNumber is None:
                if port.vid == idVendor and port.pid == idProduct:
                    portObjects.append(port)
            else:
                if port.vid == idVendor and port.pid == idProduct:
                    if re.search(serialNumber, port.serial_number, re.IGNORECASE):
                        portObjects.append(port)


        ports = []
        # portsAlreadyAdded = []
        for port in portObjects:
            # uniqueIdentifier = (port.vid, port.pid, port.serial_number)
            # if not (uniqueIdentifier in portsAlreadyAdded):                
            ports.append(port.device)
                # portsAlreadyAdded.append(uniqueIdentifier)

        return ports

    @classmethod
    def ftdiPorts(cls):
        # FIXME: for some reason, I can't get the Sutter URls with the
        # wildcard and I must handcode the following. It appears the wildcard
        # ftdi:///? does not work for some reason.
        vidpids = [(4930, 1)] # Must add custom pairs in the future.

        urls = []

        try:
            for vid, pid in vidpids:
                pyftdidevices = Ftdi.list_devices(url="ftdi://{0}:{1}/1".format(vid, pid))
                for device, address in pyftdidevices:
                    thePort = ListPortInfo(device="")
                    thePort.vid = device.vid
                    thePort.pid = device.pid
                    thePort.serial_number = device.sn
                    thePort.device = "ftdi://{0}:{1}:{2}/{3}".format(device.vid, device.pid, device.sn, address)
                    urls.append(thePort)
        except Exception as err:
            pass

        return urls

    @property
    def isOpen(self):
        if self.port is None:
            return False    
        else:
            return self.port.is_open    

    @property
    def portPathIsURL(self):
        if self.portPath is None:
            return False
        else:
            if re.match("ftdi://", self.portPath, re.IGNORECASE):
                return True
        return False

    def open(self, baudRate=57600, timeout=0.3, rtscts=False, dsrdtr=False):
        if self.port is None:
            if self.portPathIsURL:
                # See https://eblot.github.io/pyftdi/api/uart.html
                # self.portPath = re.match(r"^ftdi://0x1342:0x1/1")
                # print(self.portPath)
                self.port = pyftdi.serialext.serial_for_url(self.portPath, baudrate=baudRate, timeout=timeout)
            else:
                self.port = serial.Serial(self.portPath, baudRate, timeout=timeout, rtscts=rtscts, dsrdtr=dsrdtr)
        else:
            self.port.open()

        timeoutTime = time.time() + timeout
        while not self.isOpen:
            time.sleep(0.05)
            if time.time() > timeoutTime:
                raise UnableToOpenSerialPort()
        time.sleep(0.05)

    def close(self):
        self.port.close()

    def bytesAvailable(self) -> int:
        return self.port.inWaiting()

    def flush(self):
        if self.isOpen:
            # When an FTDI chip is used, this short sleep delay appears necessary
            # If not, the flush does not occur.
            time.sleep(0.02)
            self.port.flushInput()
            self.port.flushOutput()
            time.sleep(0.02)

    def readString(self, endPoint=0):
        with self.portLock:
            data = self.port.read_until(expected=self.terminator)

        return data.decode()

    def readData(self, length, endPoint=0) -> bytearray:
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout("Only obtained {0}".format(data))

        return data

    def writeData(self, data, endPoint=0) -> int:
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten
