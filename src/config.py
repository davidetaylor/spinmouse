import os
import tomlkit


class Config:
    """
    Read, write, and validate spinmouse_config.toml. Store runtime parameters

    The `Config` class is used to read and validate the configuration
    settings for the SpinMouse system from a TOML file.

    It a file does not exist, it creates a new configuration file with default values.

    Finally, it stores runtime paramters.

    Attributes:
        config_file_path (str): The path to the SpinMouse configuration file.
        config_file_is_new (bool): A flag that indicates whether a new configuration
            file was created.
        config_parameters_error (bool): A flag that indicates whether there is an error in 
            the config parameters.
        parameters (dict): Key-value pairs for configuration and runtime parameters

    Methods:
        _load_config_file: Loads the configuration file from disk.
        _create_config_file: Creates a new configuration file with default values.
        _validate_config: Checks the configuration parameters for validity.
    """
    def __init__(self, root_dir):
        """
        Args:
            root_dir (str): Path to root directory. Config file is assumed to be one level up.
        """
        self.config_file_path = os.path.join(os.path.dirname(root_dir), "spinmouse_config.toml")
        self.config_file_is_new = False
        self.config_parameters_error = False

        if os.path.isfile(self.config_file_path) is False:
            print("'spinmouse_config.toml' not found")
            self._create_config_file()
            self.config_file_is_new = True
        else:
            self.parameters = self._load_config_file()
            self._validate_config()

    def _load_config_file(self):
        """Loads the SpinMouse configuration file from disk.

        Returns:
            dict: key-value pairs for configuration parameters
        """
        print(f"Loading 'spinmouse_config.toml' from {self.config_file_path}\n")
        with open(self.config_file_path, mode="r") as fp:
            return tomlkit.load(fp)["parameters"]

    def _create_config_file(self):
        """Creates a new SpinMouse configuration file with default values."""
        data_path = os.path.join(os.path.dirname(self.config_file_path), "video_data")

        doc = tomlkit.document()
        doc.add(
            tomlkit.comment(
                "Spinmouse parameters. If deleted, this file will re-generate with defaults"
            )
        )
        doc.add(tomlkit.nl())

        parameters = tomlkit.table()
        parameters.add("data_directory", tomlkit.string(data_path, literal=True))
        parameters.add("video_save_framerate", 100)
        parameters["video_save_framerate"].comment("this does not affect acquisition")
        parameters.add("filename_suffix", tomlkit.string("", literal=True))
        parameters.add("use_acquisition_gui", True)

        doc.add("parameters", parameters)

        with open(self.config_file_path, mode="w") as fp:
            fp.write(tomlkit.dumps(doc))

        print(f"Config file created at {self.config_file_path}")

    def _validate_config(self):
        """Checks the configuration parameters for validity."""
        if not os.path.exists(self.parameters['data_directory']):
            print("CONFIG ISSUE: Folder defined in 'data_directory' does not exist. Please create folder or edit spinmouse_config.toml\n")
            self.config_parameters_error = True