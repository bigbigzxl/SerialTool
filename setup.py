# -*- coding: utf-8 -*-

# A simple setup script to create an executable using PyQt4. This also
# demonstrates the method for creating a Windows executable that does not have
# an associated console.
#
# PyQt4app.py is a very simple type of PyQt4 application
#
# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the application

# import sys
# from cx_Freeze import setup, Executable
#
# base = None
# if sys.platform == 'win32':
#     base = 'Win32GUI'
#
# options = {
#     'build_exe': {
#         'includes': 'atexit',
#     }
# }
#
# executables = [
#     Executable('4SiteTester.py',
#                base=base,
#                icon="sourcefile/app1.ico",
#                )
# ]
#
# setup(name='4siteTester',
#       version='1.0',
#       description='can use on serial or usb',
#       options=options,
#       executables=executables
#       )



from cx_Freeze import setup, Executable
import sys
base = None
if sys.platform == 'win32':
    base = 'Win32GUI'
base = None

executables = [Executable("4SiteTester.py", base=base, icon="sourcefile/app1.ico",)]

packages = ["idna"]
options = {
    'build_exe': {
        'packages':packages,
    },
}

setup(
    name = "<ZXL>",
    options = options,
    version = "1.2",
    description = '<QA-4site>',
    executables = executables
)