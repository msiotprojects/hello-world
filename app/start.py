
print("Hello World!")

import os
f = open("app/.version")
version = f.read()
print("version is " + version)

import subdir.subdir
print("subdir contains : " + subdir.subdir_var) 
