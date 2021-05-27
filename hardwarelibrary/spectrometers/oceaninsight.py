try:
    import time
    import numpy as np
    from struct import *
    import csv
    from typing import NamedTuple
    import array
    import re
    import os
    import sys
    import platform
    import random
    from pathlib import *

    import usb.core
    import usb.util
    import usb.backend.libusb1
    from viewer import *
    from base import *
    
except Exception as err:
    print('** Error importing modules. {0}'.format(err))
    print('We will attempt to continue and hope for the best.')
    
"""
This is a simple script to use an Ocean Insight USB2000 spectrometer. You can
use a simple interface or just use the USB2000 class and integrate it in your
own project.

If you simply run `python oceaninsight.py`, you wil get a spectrum in
real-time that you can view and save.

The USB2000 class encapsulates all the functions to access the device:  it
instantiates a communication channel with the device with PyUSB, which needs
to be installed and operational. All functions that access the USB
communication to the spectrometer start with: 'get' and 'set'. A convenience
display() function will create a SpectraViewer and call it with itself as a
parameter.  The USB2000 class can easily be used in your own program and does not
depend on GUI modules.

The SpectraViewer class includes all functions to display the spectra and manage 
user interactions. If you don't use SpectraViewer, you don't need matplotlib
or Tkinter.

Note
----

This project aims to replace the ill-conceived, shame-inducing, mind-boggingly
sucky OceanView "software"-ish that Ocean Insight appears to think is a decent option
for reasonable human beings to do science. It is not. Shame on you. On the bright
side, the OEM documentation for their spectrometers is excellent, so this 
implementation was not difficult to code.

It is in a single python file to simplify usage by others.

"""

class OISpectrometer:
    """
    An Ocean insight (Ocean Optics) spectrometer.  This allows complete access
    to the hardware with simple functions to get the spectrum, or modify the
    integration time. It is the base class for all Ocean Insight Spectrometers,
    but you will not instantiate this directly: use USB2000() or USB4000(),
    or simply: OISpectrometer.any() to get any spectrometer.
    
    Access to the device is done with pyusb and does not require any
    additional information. The USB-specific attributes of the spectrometers are
    available,  but are not needed for standard usage.  If you need to
    implement additional functions and communicate with the device (not all
    capabilities are currently coded), then you could implement them in a
    separate function.

    Methods starting with "get" and "set" will actually communication with the
    spectrometer and correspond to a command as defined in the OEM manual
    "USB2000 Data Sheet". The manuals can be found here:
    https://github.com/DCC-Lab/PyHardwareLibrary/tree/master/hardwarelibrary/manuals

    Attributes
    ----------
    idVendor: int
        USB idVendor for OceanInsight (0x2457)

    idProduct: int
        USB idProduct for spectrometer (e.g., USB2000 is 0x1002)

    wavelength: np.array(float)
        The wavelength corresponding to each pixel, as obtained from 
        factory calibration

    device : Device
        The USB device as obtained from pyusb core.find()

    configuration: Configuration
        The active USB configuration

    interface: Interface
        The active USB interface from the configuration

    serialNumber: str
        The serial number from the USB configuration descriptor

    epCommandOut: EndPoint
        The USB endpoint (i.e. the USB communication channel) to send commands

    epMainIn: EndPoint
        The USB endpoint (i.e. the USB communication channel) to receive replies
        for most commands

    epSecondaryIn: EndPoint
        The USB endpoint (i.e. the USB communication channel) to receive replies
        for spectral data and other commands

    """
    idVendor = 0x2457 # Ocean Insight USB idVendor

    # The subclasses must define a NamedTuple Status and a packingFormat
    # to retrieve and make sense of the status. See USB2000 for example.
    statusPackingFormat = None
    class Status(NamedTuple):
        pass

    timeScale = 1 # milliseconds=1, microseconds=1000

    def __init__(self, idProduct, model, serialNumber=None):
        """
        Finds and initializes the communication with the Ocean Insight spectrometer
        if there is one connected. All subclasses must provide the USB product id
        that corresponds to this model (0x1002 for USB2000 for instance) and 
        a string that describes the model, for the user.

        If two spectrometers of the same model are connected, it will match the serial
        number. If a serial number is not provided, it will take the first one. 
        This may not always be the one you expect or the same every day: it depends
        on many things that you don't control.  Just find out the serial number
        and use it.

        USB Details
        -----------

        The USB protocol is daunting for beginners and even for advanced
        programmers. It is not the place here to explain all the details,  but
        if you need to understand, here is the minimum info. The USB  protocol
        helps define the details for any device (it is *extremely* general). A device,
        when connected, needs to be configured for our purpose.

        1. A device has a "USB Configuration" that we can retrieve. 
        2. That configuration has a "USB Interface" that we pick to determine
        what we want to do with the device.
        3. That device defines communication channels (EndPoints) that are
        either input or output. Contrary to a simple serial port that has a
        single output channel and a single input channel, the USB port can
        have many  of those channels (i.e. endpoints) that can be used for
        different purpose.  For instance,  the OI Spectrometers have a channel
        for commands Input/Output and an input channel to send the data. All
        of those USB details are highly device-sepcific.  

        Ocean Insight spectrometers have 1 USB configuration descriptor only,
        we can use the default when configuring. Also, they appear to have a
        single USB interface without alternate settings, se we can use (0,0)
        to retrieve the appropriate one. Finally, reading the documentation 
        for several OI spectrometers seems to indicate that the first input
        and output channels are the main channels, and the second input
        channel is for data.

        Parameters
        ----------

        idProduct: int
            The USB product id for the spectrometer, found in the documentation
            or by connecting it.
        model: str
            A model name to be displayed to the user
        serialNumber: str Default None
            A serial number that can be used to specify which spectrometer
            we want to use when there are more than one connected. Most of the
            time, this is not needed, we simply pick the first one if no
            serial number is provided.
        """

        self.idProduct = idProduct
        self.model = model
        self.device = OISpectrometer.matchUniqueUSBDevice( idProduct=idProduct, 
                                       serialNumber=serialNumber)

        """ Below are all the USB protocol details.  This requires reading
        the USB documentation, the Spectrometer documentation and many other 
        details. What follows may sound like gibberish.

        There is a single USB Configuration (default) with a single USB Interface 
        without alternate settings, so we can use (0,0).
        """
        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        """
        We are working on the reasonable assumption from the documentation
        that the first input and output endpoints are the main endpoints and the
        second input is the data endpoint. If that is not the case, the subclass can
        simply reassign the endpoints properly in its __init__ function. 
        """
        self.inputEndpoints = []
        self.outputEndpoints = []
        for endpoint in self.interface:
            """ The endpoint address has the 8th bit set to 1 when it is an input.
            We can check with the bitwise operator & (and) 0x80. It will be zero
            if an output and non-zero if an input. """
            if endpoint.bEndpointAddress & 0x80 != 0:
                self.inputEndpoints.append(endpoint)
            else:
                self.outputEndpoints.append(endpoint)

        self.epCommandOut = None
        self.epMainIn = None
        self.epSecondaryIn = None
        self.epParameters = None
        self.epStatus = None

        if len(self.inputEndpoints) >= 2 or len(self.outputEndpoints) > 0:
            """ We have at least 2 input endpoints and 1 output. We assign the
            endpoints according to the documentation, otherwise
            the subclass will need to assign them."""
            self.epCommandOut = self.outputEndpoints[0]
            self.epMainIn = self.inputEndpoints[0]
            self.epSecondaryIn = self.inputEndpoints[1]

        self.wavelength = None
        self.discardLeadingSamples = 0 # In some models, the leading data is meaningless
        self.discardTrailingSamples = 0 # In some models, the trailing data is meaningless
        self.lastStatus = None

    def initializeDevice(self):
        """
        Initialize the Spectrometer and obtain calibration information.
        This commands needs to be sent only once per session as soon as 
        the communication is started.
        """
        try:
            self.flushEndpoints()
            self.sendCommand(b'0x01')
            time.sleep(0.1)
            self.getCalibration()
        except Exception as err:
            raise UnableToInitialize("Error when initializing device: {0}".format(err))

    def shutdownDevice(self):
        """
        Shutdown the Spectrometer. Currently does not perform anything.
        """
        return

    def flushEndpoints(self):
        for endpoint in self.inputEndpoints:
            try:
                while True:
                    buffer = array.array('B',[0]*endpoint.wMaxPacketSize)
                    endpoint.read(size_or_buffer=buffer, timeout=100)
            except usb.core.USBTimeoutError as err:
                # This is expected and is not an error if the buffers
                # are empty.
                pass
            except Exception as err:
                print("Unable to flush buffers: {0}".format(err))

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        timeInMs = int(timeInMs)
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.epCommandOut.write([0x02, lo, hi])

    def getIntegrationTime(self):
        """ Get the integration time in as a float value in milliseconds
        cls.timeScale is 1 for ms and 1000 if it is stored in µs
        """
        status = self.getStatus()
        return float(status.integrationTime)/self.timeScale

    def getSerialNumber(self):
        """ Get the serial nunmber of the spectrometer.  This can be used to
        differentiate two connected spectrometers.
        """
        return self.getParameter(index=0)

    def getCalibration(self):
        """ Get the hardcoded calibration from the spectrometer.  It is a
        3rd-order polynomial. Currently, no nonlinearities are considered.
        """
        self.a0 = float(self.getParameter(index=1))
        self.a1 = float(self.getParameter(index=2))
        self.a2 = float(self.getParameter(index=3))
        self.a3 = float(self.getParameter(index=4))
        status = self.getStatus()
        self.wavelength = [ self.a0 + self.a1*x + self.a2*x*x + self.a3*x*x*x 
                            for x in range(status.pixels)]
        if self.discardTrailingSamples > 0:
            self.wavelength = self.wavelength[:-self.discardTrailingSamples]
        if self.discardLeadingSamples > 0:
            self.wavelength = self.wavelength[self.discardLeadingSamples:]

    def getParameter(self, index):
        """ Get any of the 20 parameters hardcoded into the spectrometer.

        Parameters
        ----------

        index: int
            0 – Serial Number
            1 – 0th order Wavelength Calibration Coefficient 
            2 – 1st order Wavelength Calibration Coefficient
            3 – 2nd order Wavelength Calibration Coefficient 
            4 – 3rd order Wavelength Calibration Coefficient 
            5 – Stray light constant
            6 – 0th order non-linearity correction coefficient
            7 – 1st order non-linearity correction coefficient
            8 – 2nd order non-linearity correction coefficient
            9 – 3rd order non-linearity correction coefficient
            10 – 4th order non-linearity correction coefficient
            11 – 5th order non-linearity correction coefficient
            12 – 6th order non-linearity correction coefficient
            13 – 7th order non-linearity correction coefficient
            14 – Polynomial order of non-linearity calibration
            15 – Optical bench configuration: gg fff sss gg – Grating #, fff – filter wavelength, sss – slit size 
            16 - Spectrometer configuration: AWL V
                A – Array coating Mfg, 
                W – Array wavelength (VIS, UV, OFLV), 
                L – L2 lens installed, 
                V – CPLD Version
            17 – Reserved
            18 – Reserved
            19 – Reserved

        Returns
        -------
        parameter : str 
            The value of the parameter as an ASCII string
        """

        try:
            self.sendCommand(cmdBytes=b'\x05',
                             payloadBytes=bytearray([index]))
            parameters = self.readReply(inputEndpoint=self.epParameters,
                                        timeout=200)
            for i, c in enumerate(parameters):
                if c == 0:
                    parameters = parameters[:i]
                    break

            return bytes(parameters[2:]).decode()

        except Exception as err:
            self.flushEndpoints()
            raise UnableToCommunicate('Unable to communicate. Reset attempted {0}'.format(err))

    def requestSpectrum(self):
        """ Requests a spectrum.  The command will not return until the 
        spectrometer acknowledges that it did receive the request and flags
        it properly in its operating status. If after 1 second the request 
        has not been processed, it will raise a TimeoutError exception. """

        self.epCommandOut.write(b'\x09')
        timeOut = time.time() + 1
        while not self.isSpectrumRequested():
            time.sleep(0.001)
            if time.time() > timeOut:
                raise SpectrumRequestTimeoutError('The spectrometer never acknowledged the reception of the spectrum request')

    def isSpectrumRequested(self) -> bool:
        """ The spectrometer is currently waiting for an acquisition to 
        complete and will raise the ready flag when the spectrum is ready
        to be retrieved.

        Returns
        -------
        isSpectrumRequested : bool 
            Whether or not the spectrometer is waiting for an acquisition 
        """
        status = self.getStatus()
        return status.isSpectrumRequested

    def isSpectrumReady(self):
        """ The requested spectrum is ready to be retrieved with getSpectrumData.

        Returns
        -------
        isSpectrumReady : bool 
            Whether or not the spectrum ready to be retrieved
        """
        status = self.getStatus()
        return status.isSpectralDataReady

    def getStatus(self):
        """ The status of the spectrometer returned as a Status named tuple.

        Returns
        -------
        status : Status 
            You can access the fields of the status by index (i.e. status[0]) or
            via their names. See the `Status` class.

            pixels : int = None
            integrationTime: int = None
            isLampEnabled : bool = None
            triggerMode : int = None    
            isSpectrumRequested: bool = None
            timerSwap: bool = None
            isSpectralDataReady : bool = None
       
        """

        self.sendCommand(cmdBytes = b'\xfe')
        statusList = self.readReply(inputEndpoint=self.epStatus,
                                    unpackingFormat=self.statusPackingFormat,
                                    timeout=1000)
        status = self.Status(*statusList)
        self.lastStatus = status
        return status

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.
        This is highly device specific and must be implemented by the subclass.

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in integers corresponding to each wavelength
            available in self.wavelength.
        """
        raise NotImplementedError('You must implemented getSpectrumData for your subclass.')

    def getSpectrum(self, integrationTime=None):
        """ Obtain a spectrum from the spectrometer. This implies:
        1- changing the integration time if needed.
        2- requesting a spectrum,
        3- waiting until ready, then 
        4- actually retrieving and returning the data.
        
        Parameters
        ----------
        integrationTime: int, default None 
            integration time in milliseconds if not the currently configured
            time.

        Returns
        -------

        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
        if integrationTime is not None:
            self.setIntegrationTime(integrationTime)

        self.requestSpectrum()
        timeOut = time.time() + 1
        while not self.isSpectrumReady():
            time.sleep(0.001)
            if time.time() > timeOut:
                self.requestSpectrum() # makes no sense, let's request another one
                timeOut = time.time() + 1

        return self.getSpectrumData()

    def sendCommand(self, cmdBytes, payloadBytes=None):
        """ Main entry point to write to the device in order to have
        consistent method to manage errors. """

        buffer = bytearray()
        buffer += cmdBytes
        if payloadBytes is not None:
            buffer += payloadBytes

        try:
            self.epCommandOut.write(buffer)
        except Exception as err:
            print("Error writing to device: {0}".format(err))

    def readReply(self, inputEndpoint, size = None, unpackingFormat=None, timeout=None):
        """ Main entry point to read from device in order to have
        consistent method to manage errors. """
        if inputEndpoint is not None:
            buffer = array.array('B',[0]*inputEndpoint.wMaxPacketSize)
            try:
                if unpackingFormat is not None:
                    size = calcsize(unpackingFormat)

                if size is None:
                    inputEndpoint.read(size_or_buffer=buffer, timeout=timeout)
                else:
                    buffer = inputEndpoint.read(size_or_buffer=size, timeout=timeout)

                if unpackingFormat is not None:
                    return unpack(unpackingFormat, buffer)
                else:
                    return buffer
            except Exception as err:
                print("Error reading from device: {0}".format(err))

        return None

    def saveSpectrum(self, filepath, spectrum=None, whiteReference=None, darkReference=None):
        """ Save a spectrum to disk as a comma-separated variable file.
        If no spectrum is provided, request one from the spectrometer withoout
        changing the integration time.

        Parameters
        ----------

        filepath: str
            The path and the filename where to save the data.  If no path
            is included, the file is saved in the current directory 
            with the python script was invoked.

        spectrum: array_like
            A spectrum previously acquired or None to request a new spectrum

        whiteReference: array_like
            A white reference to normalize the measurements

        darkReference: array_like
            A dark reference for baseline

        """

        try:
            if spectrum is None:
                spectrum = self.getSpectrum()
            if darkReference is None:
                darkReference = [0]*len(spectrum)
            if whiteReference is None:
                whiteReference = [1]*len(spectrum)

            with open(filepath, 'w', newline='\n') as csvfile:
                fileWrite = csv.writer(csvfile, delimiter=',')
                fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]','White reference','Dark reference'])
                for x,y,w,d in list(zip(self.wavelength, spectrum, whiteReference, darkReference)):
                    fileWrite.writerow(["{0:.2f}".format(x),y,w,d])
        except Exception as err:
            print("Unable to save data: {0}".format(err))

    def display(self):
        """ Display the spectrum with the SpectraViewer class."""
        viewer = SpectraViewer(spectrometer=self)
        viewer.display()

    @classmethod
    def supportedClassNames(cls):
        supportedClasses = []
        for c in cls.__subclasses__():
            classSearch = re.search(r'\.(USB.*?)\W', "{0}".format(c), re.IGNORECASE)
            if classSearch:
                supportedClasses.append(classSearch.group(1))
        return supportedClasses

    @classmethod
    def showHelp(cls, err=None):
        print("""
    There may be missing modules, missing spectrometer or anything else.
    To use this `{0}` python script, you *must* have:

    1. PyUSB module installed. 
       This can be done with `pip install pyusb`.  On some platforms, you
       also need to install libusb, a free package to access USB devices.  
       On Windows, you can leave the libusb.dll file directly in the same
       directory as this script.  If no spectrometers are detected, it is
       possible the problem is due to libusb.dll not being in the directory
       where `{0}` was called.
    2. A backend for PyUSB.
       PyUSB does not communicate by itself with the USB ports of your
       computer. A 'backend' (or library) is needed.  Typically, libusb is
       used. You must  install libusb (or another compatible library). On
       macOS: type `brew install libusb` (if you have brew). If not,  get
       `brew`. On Windows/Linux, go read the PyUSB tutorial:
       https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst
       If you have libusb.dll on Windows, keep it in the same 
       directory as {0} and it should work.
    3. matplotlib module installed
       If you want to use the display function, you need matplotlib.
       This can be installed with `pip install matplotlib`
    4. Tkinter module installed.
       If you click "Save" in the window, you may need the Tkinter module.
       This comes standard with most python distributions.
    5. Obviously, a connected Ocean Insight spectrometer. It really needs to be 
       a supported spectrometer ({1}).  The details of all 
       the spectrometers are different (number of pixels, bits, wavelengths,
       speed, etc...). More spectrometers will be supported in the future.
       Look at the class USB2000 to see what you have to provide to support
       a new spectrometer (it is not that much work, but you need one to test).
""".format(__file__, ', '.join(cls.supportedClassNames())))

        # Well, how about that? This does not work in Windows
        # https://stackoverflow.com/questions/2330245/python-change-text-color-in-shell
        # if sys.stdout.isatty:
        #     err = '\x1b[{0}m{1}\x1b[0m'.format(';'.join(['33','1']), err)

        print("""    There was an error when starting: '{0}'.
    See above for help.""".format(err))

    @classmethod
    def displayAny(cls):
        spectrometer = cls.any()
        if spectrometer is not None:
            SpectraViewer(spectrometer).display()

    @classmethod
    def any(cls) -> 'OISpectrometer':
        """ Return the first supported spectrometer found as a Python object
        that can be used immediately.

        Returns
        -------
        device: subclass of OISpectrometer
            An instance of a supported spectrometer that can be used immediately.
        """

        supportedClasses = cls.__subclasses__()

        devices = cls.connectedUSBDevices()
        for device in devices:
            for aClass in supportedClasses:
                if device.idProduct == aClass.idProduct:
                    return aClass()

        if len(devices) == 0:
            raise NoSpectrometerConnected('No Ocean Optics spectrometer connected.')
        else:
            raise NoSpectrometerConnected('No supported Ocean Optics spectrometer connected. The devices {0} are not supported.'.format(devices))

    @classmethod
    def connectedUSBDevices(cls, idProduct=None, serialNumber=None):
        """ Return a list of USB devices from Ocean Insight that are currently
        connected (idVendor = 0x2457). If idProduct is provided, match only these
        products. If a serial number is provided, return the matching device otherwise
        return  an empty list. If no serial number is provided, return all devices.

        Parameters
        ----------
        idProduct: int Default: None
            The USB idProduct to match
        serialNumber: str Default: None
            The serial number to match, when there are still more than one device after
            filtering out the idProduct.  If there is a single match, the serial number
            is disregarded.

        Returns
        -------

        devices: list of Device
            A list of connected devices matching the criteria provided
        """
        if idProduct is None:
            devices = list(usb.core.find(find_all=True, idVendor=cls.idVendor))
        else:
            devices = list(usb.core.find(find_all=True, 
                                    idVendor=cls.idVendor, 
                                    idProduct=idProduct))

        if serialNumber is not None: # A serial number was provided, try to match
            for device in devices:
                deviceSerialNumber = usb.util.get_string(device, device.iSerialNumber ) 
                if deviceSerialNumber == serialNumber:
                    return [device]

            return [] # Nothing matched

        return devices

    @classmethod
    def matchUniqueUSBDevice(cls, idProduct=None, serialNumber=None):
        """ A class method to find a unique device that matches the criteria provided. If there
        is a single device connected, then the default parameters will make it return
        that single device. The idProduct is used to filter out unwanted products. If
        there are still more than one of the same product type, then the serial number
        is used to separate them. If we can't find a unique device, we raise an
        exception to suggest what to do. 

        Parameters
        ----------
        idProduct: int Default: None
            The USB idProduct to match
        serialNumber: str Default: None
            The serial number to match, when there are still more than one after
            filtering out the idProduct.  if there is a single match, the serial number
            is disregarded.

        Returns
        -------

        device: Device
            A single device matching the criteria

        Raises
        ------
            RuntimeError if a single device cannot be found.
        """

        devices = OISpectrometer.connectedUSBDevices(idProduct=idProduct, 
                                                  serialNumber=serialNumber)

        device = None
        if len(devices) == 1:
            device = devices[0]
        elif len(devices) > 1:
            if serialNumber is not None:
                raise NoSpectrometerConnected('Ocean Insight device with the appropriate serial number ({0}) was not found in the list of devices {1}'.format(serialNumber, devices))
            else:
                # No serial number provided, just take the first one
                device = devices[0]
        else:
            # No devices with criteria provided
            anyOIDevices = OISpectrometer.connectedUSBDevices()
            if len(anyOIDevices) == 0:
                raise NoSpectrometerConnected('Ocean Insight device not found because there are no Ocean Insight devices connected.'.format())
            else:
                raise NoSpectrometerConnected('Ocean Insight device not found. There are Ocean Insight devices connected {1}, but they do not match either the model or the serial number requested.'.format(anyOIDevices))

        return device


class USB2000(OISpectrometer):
    """
    A USB2000 spectrometer.  The main differences:
    1. The idProduct is 0x1002
    2. The integration time is 16-bit
    3. The format of the retrieved data is different for each spectrometer.

    """
    idProduct = 0x1002
    statusPackingFormat = '>hh?B???xxxxxxx'
    class Status(NamedTuple):
        """
        Status of the Ocean Insight USB2000 spectrometer. NamedTuple are compatible
        with regular tuples but allow access with names instead of indexes,
        simplifying usage.
        
        Attributes
        ----------
        pixels : int
            number of pixels on the sensors
        integrationTime: int
            integration time in milliseconds
        isLampEnabled : bool
            lamp strobe (connected on specific pin) is enabled
        triggerMode : int
            trigger mode: normal (freerunning, software or external)
        isSpectrumRequested: bool
            A spectrum is currently being acquired and prepared for transfer.
        timerSwap: bool
            Use an 8-bit timer or 16-bit timer for integration. Default 16-bit
        isSpectralDataReady : bool
            The spectrum requested is ready to be transferred.
        """
        pixels : int = None
        integrationTime: int = None
        isLampEnabled : bool = None
        triggerMode : int = None    
        isSpectrumRequested: bool = None
        timerSwap: bool = None
        isSpectralDataReady : bool = None

    def __init__(self):
        OISpectrometer.__init__(self, idProduct=USB2000.idProduct, model="USB2000")
        self.epParameters = self.epSecondaryIn
        self.epStatus = self.epMainIn 

        self.initializeDevice()

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.

        The format for the USB2000 is all the least significant bytes in a packet
        then the most significant bytes. We combine them to get the values.

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.epMainIn.read(size_or_buffer=64, timeout=200)
            bytesReadHi = self.epMainIn.read(size_or_buffer=64, timeout=200)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.epMainIn.read(size_or_buffer=1, timeout=200)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        self.sendCommand(cmdBytes = b'\x02',
                         payloadBytes = pack('<H',int(timeInMs)))


class USB4000(OISpectrometer):
    """
    A USB4000 spectrometer.  The main differences:
    1. The idProduct is 0x1022
    2. The integration time is 16-bit
    3. The format of the retrieved data is different for each spectrometer.

    """
    idProduct = 0x1022
    statusPackingFormat = '<hL?BBB?Bxx?x'
    timeScale = 1000 # microseconds
    class Status(NamedTuple):
        """
        Status of the USB4000 Ocean Insight spectrometer. NamedTuple are compatible
        with regular tuples but allow access with names instead of indexes,
        simplifying usage.
        
        Attributes
        ----------
        pixels : int
            number of pixels on the sensors
        integrationTime: long
            integration time in milliseconds
        isLampEnabled : bool
            lamp strobe (connected on specific pin) is enabled
        triggerMode : int
            trigger mode: normal (freerunning, software or external)
        acquisitionStatus: int
            Documentation not clear on details of this int.
        packetCount: int
            Number of packets per spectra
        powerDown: bool
            Circuit is powered down
        packetsTransferred: int
            Number of packets transferred so far
        isHighSpeed : bool
            Speed of USB communication: True is high speed. The returned format
            of the spectrum data depends on this.
        """
        pixels : int = None
        integrationTime: int = None
        isLampEnabled : bool = None
        triggerMode : int = None    
        acquisitionStatus: int = None
        packetCount: int = None
        powerDown : bool = None
        packetsTransferred: int = None
        isHighSpeed : bool = None

    def __init__(self):
        OISpectrometer.__init__(self, idProduct=USB4000.idProduct, model="USB4000")
        self.epCommandOut = self.outputEndpoints[0]
        self.epMainIn = self.inputEndpoints[2]
        self.epSecondaryIn = self.inputEndpoints[1]
        self.epParameters = self.inputEndpoints[2] 
        self.epStatus = self.inputEndpoints[2] 
        self.discardLeadingSamples = 5
        self.discardTrailingSamples = 173
        self.initializeDevice()

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.

        The format for the USB4000 is 512 bytes of integers in each packet
        followed by a single byte 0x69.

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
        spectrum = []

        if not self.lastStatus.isHighSpeed:
            raise NotImplementedError('Full speed mode not implemented for USB4000.')

        packetCount = self.lastStatus.packetCount
        exposureTime = self.lastStatus.integrationTime

        for packet in range(packetCount):
            inputEndpoint = self.inputEndpoints[0]
            if packet <= 3:
                inputEndpoint = self.inputEndpoints[1]

            values = self.readReply(inputEndpoint, unpackingFormat='<'+'H'*256, timeout=exposureTime*2)
            spectrum.extend(np.array(values))

        confirmation = self.readReply(inputEndpoint, size=1)
        if confirmation[0] != 0x69:
            self.flushEndpoints()
            raise RuntimeError('Spectrometer is desynchronized. Should disconnect')

        if self.discardTrailingSamples > 0:
            spectrum = spectrum[:-self.discardTrailingSamples]
        if self.discardLeadingSamples > 0:
            spectrum = spectrum[self.discardLeadingSamples:]

        return np.array(spectrum)

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        self.sendCommand(cmdBytes = b'\x02',
                         payloadBytes = pack('<L',int(timeInMs*self.timeScale)))

    def isSpectrumRequested(self) -> bool:
        """ The spectrometer is currently waiting for an acquisition to
        complete and will raise the ready flag when the spectrum is ready
        to be retrieved.

        The documentation for the USB4000 is not clear: the acquisition status
        is either 0,2,3,4 and it appears that 2 is when data is requested, but
        this is empirically determined.

        Returns
        -------
        isSpectrumRequested : bool
            Whether or not the spectrometer is waiting for an acquisition
        """
        while True:
            status = self.getStatus()
            if status.acquisitionStatus & 2 != 0:
                break

        return True

    def isSpectrumReady(self):
        """ The requested spectrum is ready to be retrieved with getSpectrumData.
        
        The documentation for the USB4000 is not clear: the acquisition status
        is either 0,2,3,4 and it appears that 4 is when data is ready, but
        this is empirically determined. By me.

        Returns
        -------
        isSpectrumReady : bool
            Whether or not the spectrum ready to be retrieved
        """

        while True:
            try:
                status = self.getStatus()
                if status.acquisitionStatus & 4 != 0:
                    break
            except:
                return False

        return True


class DebugSpectro:
    class Emitter(NamedTuple):
        center:float = None
        width:float = None
        intensity:float = None

    def __init__(self):
        self.model = "Debug - Nothing is connected"
        self.wavelength = np.linspace(400,1000,1024)
        self.integrationTime = 10
        self.emitters = []
        self.background = (100,200)
        for i in range(5):
            center = random.uniform(400,1000)
            width = random.uniform(2,10)
            intensity = random.uniform(10,100) # per ms
            self.emitters.append(self.Emitter(center, width, intensity))

    def getSerialNumber(self):
        return "000-000-000"

    def getSpectrum(self):
        spectrum = []
        time = self.getIntegrationTime()
        for wavelength in self.wavelength:
            intensity = 0
            for emitter in self.emitters:
                intensity += emitter.intensity*np.exp(-((wavelength-emitter.center)/emitter.width)**2)
            intensity *= time
            noise = random.gauss(0, np.sqrt(intensity))
            intensity += noise
            intensity += random.uniform(*self.background)
            if intensity > 32767:
                intensity = 32767
            spectrum.append(intensity)

        return np.array(spectrum)

    def display(self):
        """ Display the spectrum with the SpectraViewer class."""
        viewer = SpectraViewer(spectrometer=self)
        viewer.display()

    def getIntegrationTime(self):
        return self.integrationTime

    def setIntegrationTime(self, value):
        self.integrationTime = value

    def saveSpectrum(self, filepath, spectrum=None, whiteReference=None, darkReference=None):
        """ Save a spectrum to disk as a comma-separated variable file.
        If no spectrum is provided, request one from the spectrometer withoout
        changing the integration time.

        Parameters
        ----------

        filepath: str
            The path and the filename where to save the data.  If no path
            is included, the file is saved in the current directory 
            with the python script was invoked.

        spectrum: array_like
            A spectrum previously acquired or None to request a new spectrum

        whiteReference: array_like
            A white reference to normalize the measurements

        darkReference: array_like
            A dark reference for baseline

        """

        try:
            if spectrum is None:
                spectrum = self.getSpectrum()
            if darkReference is None:
                darkReference = [0]*len(spectrum)
            if whiteReference is None:
                whiteReference = [1]*len(spectrum)

            with open(filepath, 'w', newline='\n') as csvfile:
                fileWrite = csv.writer(csvfile, delimiter=',')
                fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]','White reference','Dark reference'])
                for x,y,w,d in list(zip(self.wavelength, spectrum, whiteReference, darkReference)):
                    fileWrite.writerow(["{0:.2f}".format(x),y,w,d])
        except Exception as err:
            print("Unable to save data: {0}".format(err))



def validateUSBBackend():
    backend = usb.backend.libusb1.get_backend()
    if backend is not None:
        try:
            usb.core.find(backend=backend)
            return
        except:
            pass
 
    libusbPath = None
    candidates = []
    if platform.system() == 'Windows':
        rootHardwareLibrary = PureWindowsPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/MS64/libusb-1.0.dll'),
                         rootHardwareLibrary.joinpath('communication/libusb/MS32/libusb-1.0.dll')]
    elif os.name == 'Darwin':
        rootHardwareLibrary = PurePosixPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/Darwin/libusb-1.0.0.dylib')]
    else:
        print('Cannot validate libusb backend.')

    for libpath in candidates:
        if os.path.exists(libpath):
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: "{0}".format(libpath))
            if backend is not None:
                try:
                    usb.core.find(backend=backend)
                    break
                except:
                    pass
        else:
            print("File does not exist {0}".format(libpath))

if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            validateUSBBackend() # Why not? dll's on Windows are a mess.
            spectrometer = OISpectrometer.any()
            spectrometer.getSpectrum()
        else: # any argument will do. Shh!
            spectrometer = DebugSpectro()

        spectrometer.display()

    except usb.core.NoBackendError as err:
        OISpectrometer.showHelp("PyUSB does not find any 'backend' to communicate with the USB ports (e.g., libusb is not found anywhere).")
    except NoSpectrometerConnected as err:
        OISpectrometer.showHelp("No spectrometers detected: you can use `python oceaninsight.py debug` for testing")
    except Exception as err:
        """ Something unexpected occurred, which is probably a module not available.
        We show some help and the error.
        """
        OISpectrometer.showHelp(err)
