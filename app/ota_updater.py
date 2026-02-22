import os
import gc

import adafruit_connection_manager
import adafruit_requests

import wifi

class OTAUpdater:
    """
    A class to update your MicroController with the latest version from a GitHub tagged release,
    optimized for low power usage.
    """

    def __init__(self, github_repo = None, 
                         github_src_dir='',  # used for repo/src_dir/mycode.py repo/src_dir/lib/lib.py
                         settings = None,     # dict with owner, repo name, etc
                         
                         main_dir='app',     # most client FW should like filesystem/<main_dir/>mycode.py
                         module='',          # used when client FW is in filesystem/<module/>main_dir/mycode.py
                         new_version_dir='next',         # download firware into filesystem/new_version_dir
                         new_version_file='.version'     # name of file containing current or available version
                                                        
                         secrets_file="settings.toml",    # expect this at filesystem/<secrets_file>
                 
                         headers={}    ):    # any other headers, as a dictionary.
                                             # Note that the GitHub auth header 
                                             # will be added automatically (below)
                                             # if we find GETHUB_ACCESS_TOKEN in the environment 

        if (github_repo == None) :
                # Build repo URL from settings
                if (settings == None):
                    print("OTAupdater was not given either settings or a GitHub URL");
                    return None

                repo_owner = settings["repo_owner"]
                repo_name  = settings["repo_name"]
                github_repo = "https://github.com/{}/{}".format(repo_owner,repo_name)
            


            # github_src_dir is for any top level directory in the repo above the code, lib folder, etc.
        self.github_src_dir = '' if len(github_src_dir) < 1 else github_src_dir.rstrip('/') + '/'
        
        self.module = module.rstrip('/')    # for any extra directory at the top of the filesystem
        self.main_dir = main_dir            # folder for most of the application code in the filesystem
        self.new_version_dir = new_version_dir    # where to download the firmware update
        self.new_version_file = new_version_file    # contains version tag of current or next version
        self.secrets_file = secrets_file

        # mpython orig: self.http_client = HttpClient(headers=headers)
        # Adafruit Requests replaces micropython-ota-updater htppclient.py HttpClient class 
        # with Adafruit libraries: adafruit_connection_manager, adafruit_requests

        self.headers = headers    # any headers the users finds necessary, as a dictionary
        # Support for Private Repositories :
        # This module also adds support for private repositories.
        #  Add authentication headers if authentication seems to be
        #  indicated by presence of GitHub authentication token in environment
        token_val = os.getenv("GETHUB_ACCESS_TOKEN", None) 
        if token_val :
           self.headers.update({"token": token_val})


            # Initalize Wifi, Socket Pool, Request Session
        self.pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        self.ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        self.request = adafruit_requests.Session(pool, ssl_context)
            # use "with self.request.get(url) as var"
            # where previously we used self.httpclient.get(url)
            #    was xxxx
            #    now    with self.requests.get(url) as response:
            #                do something like
            #                text = response.text
            #                json = response.json()

    

    def __del__(self):
        # mpython orig: self.http_client = None
        self.request     = None
        self.ssl_context = None
        self.pool        = None

    
    @staticmethod 
    def get_misc_settings() -> dict:

            # WIFI connection parameters
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")        # auto-connects at restart
        if (not ssid) :
            ssid = os.getenv("WIFI_SSID")                    # does not auto-connect
            
        password = os.getenv("CIRCUITPY_WIFI_PASSWORD") # auto-connects at restart
        if (not password) :
            password = os.getenv("WIFI_PASSWORD")            # does not auto-connect
            
        settings = {
            "wifi_ssid": ssid,
            "wifi_password": password,
        
                # get  GETHUB repo/access from settings.toml
            "repo_name":  os.getenv("GETHUB_REPO_NAME", "Missing_repo_name"),
            "repo_owner": os.getenv("GETHUB_REPO_OWNER", "Missing_repo_owner"),
                # optional access token allows access to private repo
            "repo_access_token": os.getenv("GETHUB_ACCESS_TOKEN", None)  ,  

                # in case we ever use Adafruit.IO for additional capabilities
            "cloud_username":    os.getenv("AIO_USERNAME", None),
            "cloud_access_key":  os.getenv("AIO_KEY", None),
        
        }
    return settings

    
    def check_for_update_to_install_during_next_reboot(self) -> bool:
        """Function which will check the GitHub repo if there is a newer version available.
        
        This method expects an active internet connection and will compare the current 
        version with the latest version available on GitHub.
        If a newer version is available, the file 'next/.version' will be created 
        and you need to call machine.reset(). A reset is needed as the installation process 
        takes up a lot of memory (mostly due to the http stack)

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        if latest_version != current_version:
            print('New version " + latest_version + " available, will download and install on next reboot')
            self._create_new_version_file(latest_version)
            return True

        return False

    def install_update_if_available_after_boot(self, ssid, password) -> bool:
        """This method will install the latest version if out-of-date after boot.
        
        This method, which should be called first thing after booting, will check if the 
        next/.version' file exists. 

        - If yes, it initializes the WIFI connection, downloads the latest version and installs it
        - If no, the WIFI connection is not initialized as no new known version is available
        """

        if self.new_version_dir in os.listdir(self.module):
            if self.new_version_file in os.listdir(self.modulepath(self.new_version_dir)):
                latest_version = self.get_version( self.modulepath(self.new_version_dir), self.new_version_file)
                print('New update found: ', latest_version)
                OTAUpdater._using_network(ssid, password)        # initialize wifi
                self.install_update_if_available()
                return True
            
        print('No new updates found...')
        return False

    def install_update_if_available(self) -> bool:
        """This method will immediately install the latest version if out-of-date.
        
        This method expects an active internet connection and allows you to decide yourself
        if you want to install the latest version. It is necessary to run it directly after boot 
        (for memory reasons) and you need to restart the microcontroller if a new version is found.

        Returns
        -------
            bool: true if a new version is available, false otherwise
        """

        (current_version, latest_version) = self._check_for_new_version()
        if latest_version != current_version:
            print('Updating fromversion {} to {}...'.format(current_version,latest_version))
            self._create_new_version_file(latest_version)
            self._download_new_version(latest_version)
            self._copy_secrets_file()
            self._delete_old_version()
            self._install_new_version()
            return True
        
        return False


    @staticmethod
    def _using_network(ssid, password):        # initialize network if  not already active
        import network    
                    # TODO: Might need to import wifi and check wifi.radio.connected instead
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print('connecting to network...')
            sta_if.active(True)
            sta_if.connect(ssid, password)
                # TODO: put a limit on how long we wait for a connection
            while not sta_if.isconnected():
                pass
        print('network config:', sta_if.ifconfig())


    

    def _check_for_new_version(self):
        current_version = self.get_version(self.modulepath(self.main_dir), self.new_version_file)
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        return (current_version, latest_version)

    def _create_new_version_file(self, latest_version): # save tag for latest_version in
                                                        # file within new_version_dir
                                                        # to indicate that a new version is available
        self.mkdir(self.modulepath(self.new_version_dir))
        with open(self.modulepath(self.new_version_dir + '/' + self.new_version_file), 'w') as versionfile:
            versionfile.write(latest_version)
            versionfile.close()

    def get_version(self, directory, version_file_name):    # retrieve version tag from file
                                                            # within existing code dirs
                                                            # OR download directory
        if version_file_name in os.listdir(directory):
            with open(directory + '/' + version_file_name) as f:
                version = f.read()
                return version    # from file
        return '0.0'    # version 0.0 if the active code was never released or updated

    def get_latest_version(self):        # retrieve tag of latest/official version from GitHub
        with self.requests.get('https://api.github.com/repos/{}/releases/latest'.format(self.github_repo)) as latest_release:
            gh_json = latest_release.json()
            try:
                version = gh_json['tag_name']
            except KeyError as e:
                raise ValueError(
                    "Release not found: \n",
                    "Please ensure release as marked as 'latest', rather than pre-release \n",
                    "github api message: \n {} \n ".format(gh_json)
                )
        latest_release.close()
        return version

    def _download_new_version(self, version):
        print('Downloading version {}'.format(version))
        self._download_all_files(version)
        print('Version {} downloaded to {}'.format(version, self.modulepath(self.new_version_dir)))

    def _download_all_files(self, version, sub_dir=''):
        url = 'https://api.github.com/repos/{}/contents{}{}{}?ref=refs/tags/{}'.format(self.github_repo, self.github_src_dir, self.main_dir, sub_dir, version)
        gc.collect() 
        with self.requests.get(url) as file_list:
            file_list_json = file_list.json()
            for file in file_list_json:
                path = self.modulepath(self.new_version_dir + '/' + file['path'].replace(self.main_dir + '/', '').replace(self.github_src_dir, ''))
                if file['type'] == 'file':
                    gitPath = file['path']
                    print('\tDownloading: ', gitPath, 'to', path)
                    self._download_file(version, gitPath, path)
                elif file['type'] == 'dir':
                    print('Creating dir', path)
                    self.mkdir(path)
                    self._download_all_files(version, sub_dir + '/' + file['name'])
                gc.collect()

        file_list.close()

    def _download_file(self, version, gitPath, path):
        with self.requests.get('https://raw.githubusercontent.com/{}/{}/{}'.format(self.github_repo, version, gitPath), saveToFile=path) as file_data:
            # save file_data into saveToFile=path, formerly done by httpclient.get
            # TODO - get file content into file, or see if adafruit request.get() can do the same
            ######################## TODO #################################
        file_data.close()
        
            
    def _copy_secrets_file(self):
        if self.secrets_file:
            fromPath = self.modulepath(self.main_dir + '/' + self.secrets_file)
            toPath = self.modulepath(self.new_version_dir + '/' + self.secrets_file)
            print('Copying secrets file from {} to {}'.format(fromPath, toPath))
            self._copy_file(fromPath, toPath)
            print('Copied secrets file from {} to {}'.format(fromPath, toPath))

    def _delete_old_version(self):
        print('Deleting old version at {} ...'.format(self.modulepath(self.main_dir)))
        self._rmtree(self.modulepath(self.main_dir))
        print('Deleted old version at {} ...'.format(self.modulepath(self.main_dir)))

    def _install_new_version(self):
        print('Installing new version at {} ...'.format(self.modulepath(self.main_dir)))
        if self._os_supports_rename():
            os.rename(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir))
        else:
            self._copy_directory(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir))
            self._rmtree(self.modulepath(self.new_version_dir))
        print('Update installed, please reboot now')

    def _rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._rmtree(directory + '/' + entry[0])
            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def _os_supports_rename(self) -> bool:
        self._mk_dirs('otaUpdater/osRenameTest')
        os.rename('otaUpdater', 'otaUpdated')
        result = len(os.listdir('otaUpdated')) > 0
        self._rmtree('otaUpdated')
        return result

    def _copy_directory(self, fromPath, toPath):
        if not self._exists_dir(toPath):
            self._mk_dirs(toPath)

        for entry in os.ilistdir(fromPath):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._copy_directory(fromPath + '/' + entry[0], toPath + '/' + entry[0])
            else:
                self._copy_file(fromPath + '/' + entry[0], toPath + '/' + entry[0])

    def _copy_file(self, fromPath, toPath):
        with open(fromPath) as fromFile:
            with open(toPath, 'w') as toFile:
                CHUNK_SIZE = 512 # bytes
                data = fromFile.read(CHUNK_SIZE)
                while data:
                    toFile.write(data)
                    data = fromFile.read(CHUNK_SIZE)
            toFile.close()
        fromFile.close()

    def _exists_dir(self, path) -> bool:
        try:
            os.listdir(path)
            return True
        except:
            return False

    def _mk_dirs(self, path:str):
        paths = path.split('/')

        pathToCreate = ''
        for x in paths:
            self.mkdir(pathToCreate + x)
            pathToCreate = pathToCreate + x + '/'


    def mkdir(self, path:str):
        if not self._exists_dir(path) :
            os.mkdir(path)
        


    def modulepath(self, path):
        return self.module + '/' + path if self.module else path
