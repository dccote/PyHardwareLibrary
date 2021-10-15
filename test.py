from hardwarelibrary.devicemanager import DeviceManager

DeviceManager().startServer()

# import usb.core

# def isCamera(dev):
#     import usb.util 
#     if dev.bDeviceClass == 0xe:
#         return True

#     for cfg in dev:
#         if usb.util.find_descriptor(cfg, bInterfaceClass=0xe) is not None:
#             return True

# for cam in usb.core.find(find_all=True, custom_match = isCamera):
#     print(cam)


# # devs = usb.core.find(find_all=True)

# # for device in devs:
# #   configuration = device.get_active_configuration()
# #   interface = configuration[(0, 0)]

# #   if interface.bInterfaceClass == 0xe :
# #       print(interface)
