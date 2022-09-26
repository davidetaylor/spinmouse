# spinmouse

## Installation instructions

1. Download SpinnakerSDK_FULL_2.7.0.128_x64.exe and spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip from https://www.flir.com/support-center/iis/machine-vision/downloads/spinnaker-sdk-and-firmware-download/.

2. Install SpinnakerSDK_FULL_2.7.0.128_x64.exe (select only Visual Studio runtimes, drivers, and SpinView)

3. Use terminal to create conda environment

    conda env create -f environment.yml

4. Use terminal to activate spinmouse environment

	conda activate spinmouse

5. Extract spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.zip and use terminal to cd to folder

6. Install PySpin

	pip install spinnaker_python-2.7.0.128-cp38-cp38-win_amd64.whl
