from src.config import Config
from src.setup import setup_experiment
from src.camera import CameraSystem
from src.acquire import run_experiment_cli, run_experiment_gui
import os
import shutil
import sys



def main():
    """
    SpinMouse entry point.

    Returns:
        bool: True, if program executed successfully. False otherwise.
    """

    print('\n===============================')
    print('=========  SpinMouse  =========')
    print('===============================\n')

    exit_status = True

    root_dir = os.path.dirname(os.path.abspath(__file__))
    config = Config(root_dir)

    if config.config_parameters_error is True:
        print("USER ACTION: There is a problem with your configuration. Address the issues above and restart\n")
        input("Press Enter to exit...")
        return False

    if config.config_file_is_new is True:
        print("USER ACTION: spinmouse_config.toml is new! Update config parameters and restart\n")
        input("Press Enter to exit...")
        return False

    MINIMUM_HD_FREE_SPACE = 10  # GB
    print(f"Remaining hard drive space: {shutil.disk_usage(config.parameters['data_directory']).free/1024**3:.1f} GB\n")
    if shutil.disk_usage(config.parameters['data_directory']).free < MINIMUM_HD_FREE_SPACE*1024**3:
        print(f"USER ACTION: There is less than {MINIMUM_HD_FREE_SPACE} GB of hard disk space remaining. Free up space and restart\n")
        input("Press Enter to exit...")
        return False

    # Connect to camera system using context manager to ensure graceful shutdown.
    with CameraSystem() as camera_system:
        if camera_system.camera is None:
            return False

        if setup_experiment(camera_system, config) is False:
            print("\n\nExperiment setup canceled: exiting system\n")
            return False

        # TODO: these functions do not return exit status
        if config.parameters['use_acquisition_gui']:
            run_experiment_gui(camera_system, config)
        else:
            run_experiment_cli(camera_system, config)

    input("\nPress Enter to exit...")

    return exit_status


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)