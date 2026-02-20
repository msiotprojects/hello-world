
# Manage writability of CIRCUITPY drive based on available button
# from https://learn.adafruit.com/circuitpython-essentials/circuitpython-storage


# This project originally used Adafruit ESP32-S3 Reverse TFT,
# which provides two buttons: D1 and D2 :
# In CircuitPython, they are available as board.D1 and board.D2.

# These two pins are pulled LOW by default, e.g. when not pressed, the signal is low. 
# When pressed, the signal goes HIGH. This is required to wake the ESP32-S3 from deep sleep. 
# This means you need to look for the signal to go high to track a button press. 
# For example, in CircuitPython, you would use if button.value:.

# By default, we want Circuit Python to be able to update firmware unattended via OTA,
# so normally, the host computer must NOT be able to write the USB drive.
#
# During development, when we wish to allow the host computer to write the drive,
#   we must press the button (on the Adafruit ESP32-S3 Reverse TFT)
#   while we reset the microcontroller



# The storage.remount() command has a readonly keyword argument. 
# This argument refers to the read/write state of CircuitPython. 
# It does NOT refer to the read/write state of your computer.
# When the value=True, the CIRCUITPY drive is read-only to CircuitPython (and writable by your computer). 
# When the value=False, the CIRCUITPY drive is writable by CircuitPython (and read-only by your computer).

# The readonly argument in boot.py is set to the value of the pin. 
import board
import digitalio
import storage

switchD2 = digitalio.DigitalInOut(board.D2)
switchD2.direction = digitalio.Direction.INPUT

# On Adafruit ESP32-S3 Reverse TFT, pressed gives True
# and readonly=True means CP cannot write the drive, but the host computer can.
# By default, the button value will be false, 
#  and CP can update files on the drive via OTA
if (switchD2.value) :
  storage.remount("/", readonly=True)
  print("D2 is pressed, host has write access to USB drive")
else
  storage.remount("/", readonly=False)
  print("D2 NOT pressed, App code can update the USB drive")

