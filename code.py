# code.py
import os, wifi

from time import sleep


print("SSID: " + os.getenv('CIRCUITPY_WIFI_SSID') )
print("Password: " + os.getenv('CIRCUITPY_WIFI_PASSWORD') )

print("connecting... or maybe already connected....")
# wifi.radio.connect(ssid=os.getenv('CIRCUITPY_WIFI_SSID'),
#                  password=os.getenv('CIRCUITPY_WIFI_PASSWORD'))
print("my IP addr:", wifi.radio.ipv4_address)

print("Scanning wifi...")
sleep(1)
networks = []
for network in wifi.radio.start_scanning_networks():
    networks.append(network)
    print(f"{len(networks)} network(s)")
    sleep(1)
    
wifi.radio.stop_scanning_networks()
networks = sorted(networks, key=lambda net: net.rssi, reverse=True)
for network in networks:
    print("ssid:",network.ssid, "rssi:",network.rssi)
    sleep(1)

import adafruit_connection_manager
import adafruit_requests

radio = wifi.radio

# Add code to make sure your radio is connected

pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
requests = adafruit_requests.Session(pool, ssl_context)
response = requests.get("http://wifitest.adafruit.com/testwifi/index.html")

# Do something with response
print(response.text)
