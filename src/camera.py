import PySpin

class CameraSystem:
    """Interface with Flir camera systems.
    
    This class partially wraps the PySpin library to interface with a camera systems
    and provides an inner class to interact with cameras.

    It can (and should) be instantiated within a context manager to ensure that
    the camera system shuts down gracefully.

    It has been tested on Flir Blackfly cameras (BFS-U3-13Y3M-C).

    If multiple cameras are connected, the user is prompted to select one of them.

    Attributes:
        system (PySpin.SystemPtr): An interface with camera system
        camera_list (PySpin.CameraList): Cameras detected by system
        num_cameras (int): The number of cameras detected by system
        camera (Camera): An instance of the Camera inner class

    Inner classes:
        Camera: Partial wrapper around the PySpin.CameraPtr object.

    """
    def __init__(self):
        """Initializes a new CameraSystem object."""
        self.system = PySpin.System.GetInstance()
        self.camera_list = self.system.GetCameras()
        self.num_cameras = self.camera_list.GetSize()

        cam = self._select_camera()
        if cam is not None:
            self.camera = self.Camera(cam)
        else:
            self.camera = None

    def __enter__(self):
        """Enters the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context manager."""
        self.close()

    def close(self):
        """Closes the camera system and releases resources."""
        print("\nReleasing camera system")

        if self.camera is not None:
            self.camera.close()

        self.camera_list.Clear()
        self.system.ReleaseInstance()

    def _select_camera(self):
        """Prompts the user to select a camera from a list of detected cameras.

        Returns:
            PySpin.CameraPtr: The selected camera or None if no cameras detected.
        """
        print("Number of cameras detected:", self.num_cameras)

        if self.num_cameras == 0:
            return None

        elif self.num_cameras == 1:
            return self.camera_list[0]

        else:
            print_format = lambda a : str(a).center(30, ' ')
            print_node_keys = ['DeviceModelName', 'DeviceSerialNumber']
            valid_cam_numbers = []

            print(*map(print_format, ['Camera'] + print_node_keys), sep = '|')
            for i,cam in enumerate(self.camera_list):
                valid_cam_numbers.append(i)
                cam_info = get_cam_info(cam)
                print_line = [i] + [cam_info.get(key) for key in print_node_keys]
                print(*map(print_format, print_line), sep = '|')

            # user selects camera
            selected_cam = None
            while selected_cam not in valid_cam_numbers:
                selected_cam = int(input(f"Select a camera from {valid_cam_numbers}: "))

            return self.camera_list[selected_cam]

    def get_cam_info(self, cam):
        """Retrieves information about the camera.

        Args:
            cam (PySpin.CameraPtr): The camera to retrieve information about.

        Returns:
            dict: A dictionary of camera information.
        """
        nodemap = cam.GetTLDeviceNodeMap()
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            cam_info = {}
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                cam_info[node_feature.GetName()] = node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'

        return cam_info


    class Camera:
        """Inner class of CameraSystem providing an iterface with a single camera.

        This class provides a partial wrapper around the PySpin camera object,

        Attributes:
            cam (PySpin.CameraPtr): An interface with the camera.

        """
        def __init__(self, cam):
            """
            Initializes a Camera object with a given PySpin CameraPtr.

            Args:
                cam (PySpin.CameraPtr): An interface with the camera.
            """
            self.cam = cam
            self._camera_acquiring_flag = False

            if cam is not None:
                try:
                    self.cam.Init()
                except PySpin.SpinnakerException as ex:
                    print("Error: %s" % ex)

        def __str__(self):
            """Returns a string representation of the Camera object"""
            return f"Camera model: {self.cam.DeviceModelName.GetValue()}, Camera serial number: {self.cam.DeviceSerialNumber.GetValue()})"

        def close(self):
            """Ends connection to the camera."""
            self.end_acquisition()
            self.cam.DeInit()
            del self.cam

        def _get_node_info(self, node):
            """Returns information about a given PySpin node as a string, if applicable.

            Args:
                node: The PySpin node to retrieve information for.

            Returns:
                str: A string representation of the node information, or None if not applicable.
            """
            if node is not None and PySpin.IsImplemented(node) and PySpin.IsReadable(node):
                return PySpin.CValuePtr(node).ToString()
            else:
                return None

        def begin_acquisition(self):
            """Begins camera acquisition if not already acquiring."""
            if self._camera_acquiring_flag is False:
                try:
                    self.cam.BeginAcquisition()
                    self._camera_acquiring_flag = True
                except PySpin.SpinnakerException as ex:
                    print("Error: %s" % ex)

        def end_acquisition(self):
            """Ends camera acquisition if currently acquiring."""
            if self._camera_acquiring_flag is True:
                try:
                    self.cam.EndAcquisition()
                    self._camera_acquiring_flag = False
                except PySpin.SpinnakerException as ex:
                    print("Error: %s" % ex)

        def get_image_settings(self, node):
            """Get attributes from image nodes

            Args:
                node (str): Name of desired image node (known to work with
                            'Width', 'Height', 'OffsetX', 'OffsetY')
            
            Returns:
                dict: A dict for node attributes ('Value', 'Min', 'Max', 'Increment')

            """
            if getattr(self.cam, node).GetAccessMode() in (PySpin.RW, PySpin.RO):
                node_attributes = {
                    'Value': getattr(self.cam, node).GetValue(),
                    'Min': getattr(self.cam, node).GetMin(),
                    'Max': getattr(self.cam, node).GetMax(),
                    'Increment': getattr(self.cam, node).GetInc()
                    }

                return node_attributes
            else:
                return None

        def update_image_offset(self, offsetx_delta, offsety_delta):
            """Update image offset relative to current offset to the closest viable offset

            Checks desired offset against valid offset values and selects the closest values

            Args:
                offsetx_delta (int or float): Number of pixels to change OffsetX
                offsety_delta (int or float): Number of pixels to change OffsetY

            """
            self.end_acquisition()  # image settings cannot be changed while acquiring

            nodemap = self.cam.GetNodeMap()

            image_settings_nodes = ['Width', 'Height', 'OffsetX', 'OffsetY']
            image_settings = {node: self.get_image_settings(node) for node in image_settings_nodes}

            desired_offsetx = image_settings['OffsetX']['Value'] + offsetx_delta
            desired_offsety = image_settings['OffsetY']['Value'] + offsety_delta


            valid_offsetx_values = [i for i in range(
                                        image_settings['OffsetX']['Min'],
                                        image_settings['OffsetX']['Max'],
                                        image_settings['OffsetX']['Increment'])
                                    ]

            valid_offsety_values = [i for i in range(
                                        image_settings['OffsetY']['Min'],
                                        image_settings['OffsetY']['Max'],
                                        image_settings['OffsetY']['Increment'])
                                    ]

            new_offsetx = min(valid_offsetx_values, key=lambda x: abs(x-desired_offsetx))
            new_offsety = min(valid_offsety_values, key=lambda y: abs(y-desired_offsety))

            node = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
            if PySpin.IsAvailable(node) and PySpin.IsWritable(node):
                node.SetValue(new_offsetx)

            node = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
            if PySpin.IsAvailable(node) and PySpin.IsWritable(node):
                node.SetValue(new_offsety)

            self.begin_acquisition()

        def enable_trigger_mode(self):
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_On)

        def disable_trigger_mode(self):
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        def enable_chunk_data(self):
            """Enable all chunk data nodes

            Refer to the PySpin ChunkData.py example for detailed explanation
            """
            nodemap = self.cam.GetNodeMap()

            try:
                result = True

                # Enable Chunk Mode
                chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode("ChunkModeActive"))
                if PySpin.IsAvailable(chunk_mode_active) and PySpin.IsWritable(chunk_mode_active):
                    chunk_mode_active.SetValue(True)

                # Enumerate "ChunkSelector", which determines which chunk is being toggled
                chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode("ChunkSelector"))
                if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
                    print("Unable to retrieve chunk selector. Aborting...\n")
                    return False

                entries = [
                    PySpin.CEnumEntryPtr(chunk_selector_entry)
                    for chunk_selector_entry in chunk_selector.GetEntries()
                ]

                for chunk_selector_entry in entries:
                    if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                        continue

                    chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
                    chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode("ChunkEnable"))

                    if not PySpin.IsAvailable(chunk_enable):
                        result = False
                    elif chunk_enable.GetValue() is True:
                        continue
                    elif PySpin.IsWritable(chunk_enable):
                        chunk_enable.SetValue(True)
                    else:
                        result = False

            except PySpin.SpinnakerException as ex:
                print("Error: %s" % ex)
                result = False

        def disable_chunk_data(self):
            """Disable all chunk data nodes

            Refer to the PySpin ChunkData.py example for detailed explanation
            """
            nodemap = self.cam.GetNodeMap()

            try:
                result = True

                # Enumerate "ChunkSelector", which determines which chunk is being toggled
                chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode("ChunkSelector"))
                if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
                    print("Unable to retrieve chunk selector. Aborting...\n")
                    return False

                entries = [
                    PySpin.CEnumEntryPtr(chunk_selector_entry)
                    for chunk_selector_entry in chunk_selector.GetEntries()
                ]

                for chunk_selector_entry in entries:
                    if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                        continue

                    chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
                    chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode("ChunkEnable"))

                    if not PySpin.IsAvailable(chunk_enable):
                        result = False
                    elif chunk_enable.GetValue() is False:
                        continue
                    elif PySpin.IsWritable(chunk_enable):
                        chunk_enable.SetValue(False)
                    else:
                        result = False

                chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode("ChunkModeActive"))
                if PySpin.IsAvailable(chunk_mode_active) and PySpin.IsWritable(chunk_mode_active):
                    chunk_mode_active.SetValue(False)

            except PySpin.SpinnakerException as ex:
                print("Error: %s" % ex)
                result = False
