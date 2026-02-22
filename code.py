

# Based on MicroPython OTAUpdater, 
# connectToWifiAndUpdate() below assumes that immediatly on reset, 
# we want to connect to wifi,  check for update, and install it.
#      CircuitPython will auto-connect to wifi on restart IF
#      you have CIRCUITPY_WIFI_SSID and CIRCUITPY_WIFI_PASSWORD set up
#      in your settings.toml file, but auto-connect is not necessary.
#
# There is also install_update_if_available_after_boot()
# which checks to see if a pending update was noted in a previous wifi connection,
# and does not initialize wifi if there is no indication of an available update.

def connectToWifiAndUpdate():
    import time,  gc
    time.sleep(1)
    print('Memory free', gc.mem_free())

    from app.ota_updater import OTAUpdater

    

    print('Memory free', gc.mem_free())
    # If desired, you can pass the GitHub repo and other parameters here,
    # but if you do not, they will be obtained from environment variables
    # initialized from the settings.toml (default secrets) file in get_misc_settings()
    settings = OTAUpdater.get_misc_settings()

        # initialize network if not already active
    OTAupdate._using_network(settings["wifi_ssid"], settings["wifi_password"))
    
    # Micropython OTAUpdater passed ( 'https://github.com/owner_name/repo_name', main_dir='app', secrets_file="secrets.py")
    otaUpdater = OTAUpdater(settings = settings, github_repo = None)
    
    hasUpdated = otaUpdater.install_update_if_available()
    if hasUpdated:
        machine.reset()
    else:
        del(otaUpdater)
        gc.collect()

def startApp():
    import app.start        # sorry - this assumes that most code is in app/ subdir


connectToWifiAndUpdate()
startApp()
