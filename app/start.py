
print("Hello World!")

import os
from time import sleep

f = open("app/.version")
version = f.read()
print("version file contains: " + version)
sleep(5)

import app.subdir.subdir
print("subdir contains : " + subdir_var) 
