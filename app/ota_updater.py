import os
import gc

import adafruit_connection_manager
import adafruit_pathlib
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
                         
                         main_dir='app',     # most client FW should in filesystem at /<main_dir/>mycode.py
                         module='',          # used when client FW is in filesystem at /<module/><main_dir/>mycode.py
                         new_version_dir='next',         # download firware into filesystem/new_version_dir
                         new_version_file='.version' ,   # name of file containing current or available version
                                                        
                         secrets_file="settings.toml",    # expect this in filesystem at <secrets_file>
                                                          # As parameter, include any other path component,
                                                          # e.g. /app/secrets.txt
                 
                         headers={}    ):    # any other headers, as a dictionary.
                                             # Note that the GitHub auth header 
                                             # will be added automatically (below)
                                             # if we find GETHUB_ACCESS_TOKEN in the environment 

        if (github_repo) :
            self.github_repo = github_repo.rstrip('/').replace('https://github.com/', '')
        else :
                # Build repo from settings
                if (settings == None):
                    print("OTAupdater was not given either settings or a GitHub URL");
                    return None

                repo_owner = settings["repo_owner"]
                repo_name  = settings["repo_name"]
                self.github_repo = "{}/{}".format(repo_owner,repo_name)
            


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
        self.requests = adafruit_requests.Session(self.pool, self.ssl_context)
            # use "with self.requests.get(url) as var"
            # where previously we used self.httpclient.get(url)
            #    was xxxx
            #    now    with self.requests.get(url) as response:
            #                do something like
            #                text = response.text
            #                json = response.json()

    

    def __del__(self):
        # mpython orig: self.http_client = None
        self.requests    = None
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
            if not self._download_new_version(latest_version):
                print("Could not download latest version " + latest_version )
                return False
            if not self._copy_secrets_file() :
                print("Could not back up secrets file")
                return False
                
            if not self._delete_old_version() :
                print("OLD VERSION MAY BE PARTIALLY DELETED")
                return False
            
            if not self._install_new_version() :
                print("Could not install new version " + latest_version )
                return False
            
            return True    # Update was installed 
        
        return False    # OK, but Update not available


    @staticmethod
    def _using_network(ssid, password):        # initialize network if  not already active
        # micropython: import network    

        import wifi
        
        if not wifi.radio.connected:
            print('connecting to network...')
            try:
                wifi.radio.connect(ssid, password)
                
            except ConnectionError as e:
                print("wifi connect error:",e)
                return False
                              
        print('Connected to WIFI as ', wifi.radio.ipv4_address)
        return True


    

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
        github_url = 'https://api.github.com/repos/{}/releases/latest'.format(self.github_repo)
        with self.requests.get(github_url) as latest_release:
            gh_json = latest_release.json()
            try:
                version = gh_json['tag_name']
            except KeyError as e:
                raise ValueError(
                    "Release not found: \n",
                    " URL was " + github_url + "\n" ,
                    "Please ensure release as marked as 'latest', rather than pre-release \n",
                    "github api message: \n {} \n ".format(gh_json)
                )
        latest_release.close()
        return version

    def _download_new_version(self, version):
        newdir = self.modulepath(self.new_version_dir)
        print('Downloading version {} to {}'.format(version,newdir))
        if self._download_all_files(version):
            print('Version {} downloaded to {}'.format(version, newdir))
            return True
        print('Version {} FAILED to download cleanly to {}'.format(version, newdir))
        return False

    def _download_all_files(self, version, sub_dir=''):
        ret_status = True   # return status: assume that nothing fails
        
        # root_url = self.github_repo + '/contents/' + self.github_src_dir + self.main_dir + sub_dir
        url = 'https://api.github.com/repos/{}/contents/{}{}{}?ref=refs/tags/{}'.format(self.github_repo, self.github_src_dir, self.main_dir, sub_dir, version)
        print(" download URL " + url)
        gc.collect() 
        with self.requests.get(url) as file_list:
            file_list_json = file_list.json()
            # print("json: "); print(file_list_json)
            for file in file_list_json:
                # print("file is ") ; print(file)
                fname = file['path']
                # print("Download " + fname )
                path = self.modulepath(self.new_version_dir + '/' + file['path'].replace(self.main_dir + '/', '').replace(self.github_src_dir, ''))
                if file['type'] == 'file':
                    gitPath = file['path']
                    print('Downloading: ', gitPath, 'to', path)
                    if not self._download_file(version, gitPath, path):
                        ret_status = False
                elif file['type'] == 'dir':
                    print('Creating dir', path)
                    if self.mkdir(path):
                        if not self._download_all_files(version, sub_dir + '/' + file['name']) :
                            ret_status = False
                        
                gc.collect()

        file_list.close()
        return ret_status

    

    def _download_file(self, version, gitPath, path):
        git_file_url = 'https://raw.githubusercontent.com/{}/{}/{}'.format(self.github_repo, version, gitPath)
        # with self.requests.get('https://raw.githubusercontent.com/{}/{}/{}'.format(self.github_repo, version, gitPath), saveToFile=path) as file_data:
        try:
            with self.requests.get( git_file_url ) as file_data :
                #file_data.raise_for_status()     # notice bad responses
                # raise_for_status() not working with GitHub(?):
                # always get exception :
                #  'Response' object has no attribute 'raise_for_status'
                code = file_data.status_code
                if ((code < 200) or (code > 299)):
                        print(f"Bad status {code} from {git_file_url}")
                        file_data.close()
                        return False
                   

                # save file_data into saveToFile=path, formerly done by httpclient.get in micropython version
                # TODO - get file content into file, or see if adafruit request.get() can do the same
                ######################## TODO #################################
                # We open file as binary in case the content is not text (e.g. a compiled library)
                # and hope that it is legitimate to copy text this way too,
                # rather than as file_data.text 
                try:
                    with open(path, "wb") as file :
                        # file.raise_for_status()    # notice bad file opens
                        # raise_for_status() not working with files?
                        # always get exception : 
                        #  'FileIO' object has no attribute 'raise_for_status'
                        file.write(file_data.content)
                    
                    print("\tCopied file " + path)
                except Exception as f: 
                    print(f"A file could not be opened : {f}")
                    return False

        except Exception as e:
                print(f"Cannot get data from {git_file_url}: {e}")
                return False

        return True
        
            
    def _copy_secrets_file(self):
        # if secrets_file (which is supposed to include its path)
        # is in main_dir then 
        #  1) it will be removed when the old version is removed 
        #     before the new one can be installed.
        #  2) it will probably NOT be in the Git repository
        #     so we will not get a fresh one by downloading.
        # (if it is not in main_dir, then there's no problem)
        #
        # When it looks like there will be a problem,
        # we copy it into the new_version_dir prior to removal,
        # otherwise we leave it alone.
        if not self.secrets_file:
            return True        # no secrets to copy, succeed
            
        # find out if secrets file is somewhere in main_dir
        words = self.secrets_file.split("/")    # split path into words on /
        if not (self.main_dir in words) :
            # main_dir not part of path to secrets, nothing to do
            return True

        # copy secrets file into new_version_dir
        fromPath = self.modulepath(self.secrets_file)  # filename should include path
        toPath = self.modulepath(self.new_version_dir + '/' + self.secrets_file)             
            
        print('Copying secrets file from {} to {}'.format(fromPath, toPath))
        if self._copy_file(fromPath, toPath):
            print('Copied secrets file from {} to {}'.format(fromPath, toPath))
            return True

        return False    # failed to copy secrets

    

    def _delete_old_version(self):
        retStat = True        # assume good return status
        print('Deleting old version at {} ...'.format(self.modulepath(self.main_dir)))
        if self._rmtree(self.modulepath(self.main_dir)):
            action = "Deleted"
        else:
            action = "FAILED to delete"
            retStat = False
            
        print('{} old version at {} ...'.format(action,self.modulepath(self.main_dir)))   
        return retStat

    
    def _install_new_version(self):
        retStat = True
        print('Installing new version at {} ...'.format(self.modulepath(self.main_dir)))
        if self._os_supports_rename():
            try:
                os.rename(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir))
            except:
                print("Unable to rename {} as {}".format(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir)))
                retStat = False
        else:
            if not self._copy_directory(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir)):
                print("Cannot copy {} to {}".format(self.modulepath(self.new_version_dir), self.modulepath(self.main_dir)))
                retStat = False
            else:    
                if not self._rmtree(self.modulepath(self.new_version_dir)):
                    retStat = False 
        if retStat :
            print('Update installed, please reboot now')
        else:
            print('   UPDATE FAILED: DO NOT REBOOT WITHOUT EXAMINING SYSTEM ')
            
        return retStat
        

    def _rmtree(self, directory):
        retStat = True    # assume good return status
        print("Enter _rmtree " + directory)
        if not directory:
            return True    # nothing to remove, pretend
        for entry in os.listdir(directory):
              entryPath = directory + "/" + entry
              Path = adafruit_pathlib.Path(entryPath)
              if Path.is_dir() :
                    print("  Call rmtree " + entryPath )
                    if not self._rmtree(entryPath):
                        retStat = False
                        print("FAILED to rmtree " + entryPath)
              else:
                  print("   Call remove " + entryPath )
                  try:
                      os.remove(entryPath)
                  except:
                    retStat = False
                    print("FAILED to remove " + entryPath)
                      
        try:
            os.rmdir(directory)
        except:
            retStat = False
            print("FAILED to _rmtree " + directory)

        return retStat

    
      

    def _os_supports_rename(self) -> bool:
        self._mk_dirs('otaUpdater/osRenameTest')
        os.rename('otaUpdater', 'otaUpdated')
        result = len(os.listdir('otaUpdated')) > 0
        self._rmtree('otaUpdated')
        return result

    def _copy_directory(self, fromPath, toPath):
        if not self._exists_dir(toPath):
            if not self._mk_dirs(toPath):
                return False

        for entry in os.listdir(fromPath):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self._copy_directory(fromPath + '/' + entry[0], toPath + '/' + entry[0])
            else:
                self._copy_file(fromPath + '/' + entry[0], toPath + '/' + entry[0])


    
    def _copy_file(self, fromPath, toPath):
        retStat = True    # good return status until proven otherwise
        try:
            with open(fromPath) as fromFile:
                try:
                    with open(toPath, 'w') as toFile:
                        CHUNK_SIZE =     512 # bytes
                        data = fromFile.read(CHUNK_SIZE)
                        try:
                            while data:
                                toFile.write(data)
                                data = fromFile.read(CHUNK_SIZE)
                        except:
                            print("Could not write data into " + toPath)
                            retStat = False
                    
                except:
                    print("Could not open target file " + toPath)
                    retStat = False
            
        except:
            print("Could not open source file " + fromPath)
            retStat = False

        return retStat
        

    
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
