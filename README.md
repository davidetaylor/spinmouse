# spinmouse
Software to acquire high-speed mouse behavior video using FLIR Blackfly cameras


## Installation

Go with this option if you want to run the software on an acquisition computer. If you want to modify the code, install the [full developement environment](#installing-full-development-environment).

1. Download `SpinnakerSDK_FULL_2.7.0.128_x64.exe` and `spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip` from https://www.flir.com/support-center/iis/machine-vision/downloads/spinnaker-sdk-and-firmware-download/.

2. Install `SpinnakerSDK_FULL_2.7.0.128_x64.exe`

3. Download the latest `spinmouse-x.y.z.zip` one-folder distribution. Upzip the folder and put it somewhere that makes sense, such as a folder on the desktop called "spinmouse". I like to create a shortcut for `spinmouse-x.y.z/spinmouse-x.y.z.exe` and put it in the folder containing the `spinmouse-x.y.z` folder.


### Installing full development environment

Go with this option if you want to develop the software.

1. Download `SpinnakerSDK_FULL_2.7.0.128_x64.exe` and `spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip` from https://www.flir.com/support-center/iis/machine-vision/downloads/spinnaker-sdk-and-firmware-download/.

2. Install `SpinnakerSDK_FULL_2.7.0.128_x64.exe`

3. Use terminal to create conda environment

		conda env create -f environment.yml

4. Use terminal to activate spinmouse environment

		conda activate spinmouse

5. Extract `spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip` and use terminal to cd to folder

6. Install PySpin

		pip install spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.whl

7. Clone or download spinmouse source code from this repository.


## Building new one-folder distributions

1. Install the [full developement environment](#installing-full-development-environment).
2. Make sure the spinmouse conda environment is activated.
3. Use pyinstaller to package spinmouse:

		pyinstaller spinmouse.py --name spinmouse-x.y.z --collect-all PySpin
		
4. Pyinstaller will create build and dist folders, as well as a .spec file. build and .spec files can be ignored. Inside of dist will be a single folder called `spinmouse-x.y.z` that can be copied to other computers.


## Notes for future development

- I have been unable to get Flea3 cameras to reliably provide chunk data (i.e., timestamps). I've communicated extensively with Flir and tested many possible solutions without success. Newer firmware versions (i.e., 2.15.3.4) support chunk data, but I experienced reliability issues, such as volatile camera settings.

- One-folder spinmouse distributions do not work on Windows 7 machines because because pyinstaller programs created on Windows 10 are not compatible with Windows 7 (which is obsolete and should be avoided anyway).

- pyinstaller appears to not include some Spinnaker libaries, so you need to have the Full 64-bit Spinnaker SDK installed (not just SpinView) in order for it to work. Otherwise, an error will instruct you to check that the FLIR_GENTL64_CTI_VS140 system variable points to FLIR_GenTL_v140.cti, which is only present if you install the full 64-bit Spinnaker SDK (C:\Program Files\FLIR Systems\Spinnaker\cti64\vs2015\FLIR_GenTL_v140.cti).