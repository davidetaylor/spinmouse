# spinmouse

## Installation
1. [Self-contained binary](#installation-option-1-binary): This is the best option for acquisition computers!
2. [Full development environment](#installation-option-2-full-development-environment)

## Installation Option 1: Binary

Download the latest `spinmouse-x.y.z.exe` binary. Data files will be saved in the same directory, so put the binary in a subfolder somewhere that makes sense.

## Installation Option 2: Full Development Environment

1. Download `SpinnakerSDK_FULL_2.7.0.128_x64.exe` and `spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip` from https://www.flir.com/support-center/iis/machine-vision/downloads/spinnaker-sdk-and-firmware-download/.

2. Install `SpinnakerSDK_FULL_2.7.0.128_x64.exe` (select only Visual Studio runtimes, drivers, and SpinView)

3. Use terminal to create conda environment

		conda env create -f environment.yml

4. Use terminal to activate spinmouse environment

		conda activate spinmouse

5. Extract `spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip` and use terminal to cd to folder

6. Install PySpin

		pip install spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.whl

## Creating New Binaries

1. Install the [full developement environment](#installation-option-2-full-development-environment)
2. Make sure the spinmouse conda environment is activated.
3. Use pyinstaller to package spinmouse:

		pyinstaller spinmouse.py --onefile --collect-all PySpin
		
4. Pyinstaller will create build and dist folders, as well as a .spec file. build and .spec files can be ignored. Inside of dist will be a single file called spinmouse-x.y.z.exe that can be copied to other computers.
5. (optional) For troubleshooting purposes, you can use pyinstaller to create a one-folder distribution instead of a one-file distribution. Pyinstaller will create build and dist folders, as well as a .spec file. build and .spec files can be ignored. Inside of dist will be a folder called spinmouse containing all of the files necessary to run spinmouse. The spinmouse folder can be copied to other computers and run using the spinmouse.exe file.

		pyinstaller spinmouse.py --collect-all PySpin
