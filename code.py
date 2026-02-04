# code.py
import os, wifi
print("SSID: " + os.getenv('CIRCUITPY_WIFI_SSID') )
print("Password: " + os.getenv('CIRCUITPY_WIFI_PASSWORD') )

print("connecting... or maybe already connected....")
# wifi.radio.connect(ssid=os.getenv('CIRCUITPY_WIFI_SSID'),
#                  password=os.getenv('CIRCUITPY_WIFI_PASSWORD'))
print("my IP addr:", wifi.radio.ipv4_address)

print("hello, world")
