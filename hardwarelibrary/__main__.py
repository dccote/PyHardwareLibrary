import os 
import sys
import argparse
import re
import subprocess
from pathlib import Path
import platform
import hardwarelibrary.spectrometers as spectro
from hardwarelibrary import DeviceManager

import signal
import sys

def signal_handler(sig, frame):
    print('Quitting nicely !')
    dm = DeviceManager()
    try:
        dm.stopMonitoring()
    except Exception as err:
        print(err)
    try:
        dm.stopServer()
    except Exception as err:
        print(err)

signal.signal(signal.SIGINT, signal_handler)

 # We start by figuring out what the user really wants. If they don't know,
# we offer some help
ap = argparse.ArgumentParser(prog='python -m hardwarelibrary')
ap.add_argument("-stellar", "--stellarnet", required=False, action='store_const',
                const=True, help="Decrypt the StellarnNet driver.  Contact StellarNet for info.")
ap.add_argument("-s", "--spectrometer", required=False, action='store_const',
                const=True, help="Display any spectrometer")
ap.add_argument("-dm", "--devicemanager", required=False, action='store_const',
                const=True, help="Show notifications from DeviceManager")

args = vars(ap.parse_args())
decrypt = args['stellarnet']
displaySpectrum = args['spectrometer']
deviceManager = args['devicemanager']

if decrypt == True:
    rootHardwareLibrary = Path(os.path.abspath(__file__)).parents[1]
    spectrometersDirectory = rootHardwareLibrary.joinpath('hardwarelibrary/spectrometers')
    zipFile =spectrometersDirectory.joinpath('stellarnet.zip')

    if platform.system() == 'Windows':
        os.startfile(zipFile)
    elif platform.system() == 'Darwin':
        completedProcess = subprocess.run(["unzip", zipFile, "-d", spectrometersDirectory])
        if completedProcess.returncode != 0:
            print("There was an error when unzipping and decrypting the stellarnet.zip file")
    else:
        print('Cannot unzip stellarnet file')

if displaySpectrum == True:
    spectro.displayAny()

if deviceManager == True:
    dm = DeviceManager()
    dm.showNotifications()
    dm.startMonitoring()
    dm.startServer()

