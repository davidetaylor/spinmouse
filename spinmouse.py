# -*- coding: utf-8 -*-
import PySpin
import sys
import os
import csv
import time
import keyboard
import threading
from collections import deque
import cv2
import numpy as np


AVI_SAVE_FRAME_RATE = 100 # this only affects the frame rate of the video, not the acquisition

class FrameCounter():
    """
    This class tracks acquired, buffered, and dropped frames.
    """
    def __init__(self):
        self.acquired = 0
        self.buffered = 0
        self.dropped = 0

        self.last_frameid = None

    # Call this method each time a frame is saved
    def update(self, queue_len: int, frameid: int):
        self.acquired += 1
        self.buffered = queue_len
        
        if self.last_frameid == None:
            self.last_frameid = frameid
        else:
            self.dropped += frameid - self.last_frameid - 1
            self.last_frameid = frameid

    # Call this method to display the current counter values
    def print(self):
        acquired = str(self.acquired).rjust(12, ' ')
        buffered = str(self.buffered).rjust(12, ' ')
        dropped = str(self.dropped).rjust(12, ' ')
        print(f"Acquired: {acquired}  |  Buffered: {buffered}  |  Dropped: {dropped}")


def save_images(acquisition_complete_event, file_name, images_queue, nodemap):
    """
    This function prepares, saves, and cleans up an AVI video from a deque of images,
    saves timestamp data to CSV, and tracks acquired/buffered/dropped frames.

    Uses OpenCV + FFMPEG to save video.
    
    :param stop_event (type: threading.Event): Thread safe boolean to signal acquisition stop
    :param nodemap (type: INodeMap): Device nodemap.
    :param file_name (type: Str): Base experiment file name
    :param images_queue (type: collections.deque of ImagePtr): Thread safe buffer for image data

    :return (type: bool): True if successful, False otherwise.
    """

    try:
        result = True

        # get image height/width
        node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height')).GetValue()
        node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width')).GetValue()
        print(node_height)
        print(node_width)

        # open AVI with unique filename
        frame_size = (node_width, node_height)
        video_recorder = cv2.VideoWriter(file_name+".avi", cv2.CAP_FFMPEG, cv2.VideoWriter_fourcc('M','J','P','G'), 100.0, frame_size, 0)

        # open log csv
        logfile = open(file_name + '_timestamps.csv', 'w', newline='')
        log_writer = csv.writer(logfile)

        # Initialize frame counter
        frame_counter = FrameCounter()

        # Video/timestamp saving loop
        while True:
            if len(images_queue) > 0:
                new_image = images_queue.popleft()
                video_recorder.write(new_image.GetNDArray().T)

                # append frame chunk data to log csv
                frame_id, timestamp = get_id_timestamp_from_chunk_data(new_image)
                log_writer.writerow((frame_id, timestamp))

                # update frame counter and print
                frame_counter.update(len(images_queue), frame_id)
                frame_counter.print()

            else:
                if acquisition_complete_event.is_set():
                    break
                else:
                    time.sleep(0.01)

        # Close log file
        logfile.close()

        # Close AVI file
        video_recorder.release()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def acquire_images(acquisition_complete_event, cam, nodemap, images_queue):
    """
    
    
    :param cam (type: CameraPtr): Camera to acquire images from.
    :param nodemap (type: INodeMap): Device nodemap.
    :param stop_event (type: threading.Event): Thread safe boolean to signal acquisition stop
    :param images_queue (type: collections.deque of ImagePtr): Thread safe buffer for image data

    :return (type: bool): True if successful, False otherwise.
    """

    frames_acquired = 0
    
    print('*** IMAGE ACQUISITION ***\n')
    try:
        result = True

        #  Begin acquiring images
        cam.BeginAcquisition()

        print('Acquiring images...')

        images = list()

        # Retrieve, convert, and save images
        while True:
        # for i in range(NUM_IMAGES):

            try:
                #  Retrieve next received image
                image_result = cam.GetNextImage(1000)

                #  Ensure image completion
                if image_result.IsIncomplete():
                    print('Image incomplete with image status %d...' % image_result.GetImageStatus())

                else:
                    #  Print image information; hieght and width recorded in pixels
                    print('Grabbed Image')

                    #  Convert image to mono 8 and append to list
                    # images_queue.put(image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR))
                    images_queue.append(image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR))
                    
                    #  Release image
                    image_result.Release()
                    print('')

                    frames_acquired += 1

            except PySpin.SpinnakerException as ex:
                print('Error: %s' % ex)
                result = False

            if keyboard.is_pressed("p"):
                print("You pressed p")
                print("Frames acquired: %d" % (frames_acquired))
                acquisition_complete_event.set()
                break

        # End acquisition
        cam.EndAcquisition()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result








def configure_chunk_data(nodemap):
    """
    This function configures the camera to add chunk data to each image. It does
    this by enabling each type of chunk data before enabling chunk data mode.
    When chunk data is turned on, the data is made available in both the nodemap
    and each image.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise
    :rtype: bool
    """
    try:
        result = True
        print('\n*** CONFIGURING CHUNK DATA ***\n')

        # Activate chunk mode
        #
        # *** NOTES ***
        # Once enabled, chunk data will be available at the end of the payload
        # of every image captured until it is disabled. Chunk data can also be
        # retrieved from the nodemap.
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))

        if PySpin.IsAvailable(chunk_mode_active) and PySpin.IsWritable(chunk_mode_active):
            chunk_mode_active.SetValue(True)

        print('Chunk mode activated...')

        # Enable all types of chunk data
        #
        # *** NOTES ***
        # Enabling chunk data requires working with nodes: "ChunkSelector"
        # is an enumeration selector node and "ChunkEnable" is a boolean. It
        # requires retrieving the selector node (which is of enumeration node
        # type), selecting the entry of the chunk data to be enabled, retrieving
        # the corresponding boolean, and setting it to be true.
        #
        # In this example, all chunk data is enabled, so these steps are
        # performed in a loop. Once this is complete, chunk mode still needs to
        # be activated.
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))

        if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
            print('Unable to retrieve chunk selector. Aborting...\n')
            return False

        # Retrieve entries
        #
        # *** NOTES ***
        # PySpin handles mass entry retrieval in a different way than the C++
        # API. Instead of taking in a NodeList_t reference, GetEntries() takes
        # no parameters and gives us a list of INodes. Since we want these INodes
        # to be of type CEnumEntryPtr, we can use a list comprehension to
        # transform all of our collected INodes into CEnumEntryPtrs at once.
        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]

        print('Enabling entries...')

        # Iterate through our list and select each entry node to enable
        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())

            chunk_str = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Enable the boolean, thus enabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_str))
                result = False
            elif chunk_enable.GetValue() is True:
                print('{} enabled'.format(chunk_str))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(True)
                print('{} enabled'.format(chunk_str))
            else:
                print('{} not writable'.format(chunk_str))
                result = False

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result



def get_id_timestamp_from_chunk_data(image):
    """
    This function displays a select amount of chunk data from the image. Unlike
    accessing chunk data via the nodemap, there is no way to loop through all
    available data.

    :param image: Image to acquire chunk data from
    :type image: Image object
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
##        result = True
        
        # Retrieve chunk data from image
        chunk_data = image.GetChunkData()

        # Retrieve frame ID
        frame_id = chunk_data.GetFrameID()
##        print('\tFrame ID: {}'.format(frame_id))

        # Retrieve timestamp
        timestamp = chunk_data.GetTimestamp()
##        print('\tTimestamp: {}'.format(timestamp))

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
##        result = False
    return frame_id, timestamp



def disable_chunk_data(nodemap):
    """
    This function disables each type of chunk data before disabling chunk data mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise
    :rtype: bool
    """
    try:
        result = True

        # Retrieve the selector node
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))

        if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
            print('Unable to retrieve chunk selector. Aborting...\n')
            return False

        # Retrieve entries
        #
        # *** NOTES ***
        # PySpin handles mass entry retrieval in a different way than the C++
        # API. Instead of taking in a NodeList_t reference, GetEntries() takes
        # no parameters and gives us a list of INodes. Since we want these INodes
        # to be of type CEnumEntryPtr, we can use a list comprehension to
        # transform all of our collected INodes into CEnumEntryPtrs at once.
        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]

        print('Disabling entries...')

        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())

            chunk_symbolic_form = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Disable the boolean, thus disabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_symbolic_form))
                result = False
            elif not chunk_enable.GetValue():
                print('{} disabled'.format(chunk_symbolic_form))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(False)
                print('{} disabled'.format(chunk_symbolic_form))
            else:
                print('{} not writable'.format(chunk_symbolic_form))

        # Deactivate Chunk Mode
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))

        if not PySpin.IsAvailable(chunk_mode_active) or not PySpin.IsWritable(chunk_mode_active):
            print('Unable to deactivate chunk mode. Aborting...\n')
            return False

        chunk_mode_active.SetValue(False)

        print('Chunk mode deactivated...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result




def print_device_info(nodemap):
    """
    This function prints the device information of the camera from the transport
    layer; please see NodeMapInfo example for more in-depth comments on printing
    device information from the nodemap.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    print('\n*** DEVICE INFORMATION ***\n')

    try:
        result = True
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not available.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def run_single_camera(cam,file_name):
    """
    This function acts as the body of the example; please see NodeMapInfo example
    for more in-depth comments on setting up cameras.

    :param cam: Camera to run example on.
    :type cam: CameraPtr
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    try:
        result = True

        # Retrieve TL device nodemap and print device information
        nodemap_tldevice = cam.GetTLDeviceNodeMap()

        result &= print_device_info(nodemap_tldevice)

        # Initialize camera
        cam.Init()

        # Retrieve GenICam nodemap (take care - some of these nodes are mutable and can change camera function)
        nodemap = cam.GetNodeMap()

        # TODO: Setup GUI for adjusting roi, setting filename, etc. All parameter adjustments done here. Software frame triggers

        # Configure chunk data
        if configure_chunk_data(nodemap) is False:
            return False

        # Create infinitely large image buffer queue
        # images_queue = queue.Queue(maxsize=0)
        images_queue = deque([])

        # Create an thread event to signal when acquisition is complete
        acquisition_complete_event = threading.Event()

        # Create threads for acquiring and saving images
        acquire_images_thread = threading.Thread(target=acquire_images, args=[acquisition_complete_event, cam, nodemap, images_queue])
        save_images_thread = threading.Thread(target=save_images, args=[acquisition_complete_event, file_name, images_queue, nodemap])
        acquire_images_thread.start()
        save_images_thread.start()
        acquire_images_thread.join()
        save_images_thread.join()

        # Disable chunk data
        if disable_chunk_data(nodemap) is False:
            return False

        # Deinitialize camera
        cam.DeInit()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result



def main():
    """
    Entry point; preps and cleans up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """
    result = True

    # TODO: move this to Setup GUI
    # set filename
    file_name = input("Enter filename (e.g., YYYYMMDD_##_IDNum): ")
    file_name = file_name + "_BodyCam"
    
    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()
    num_cameras = cam_list.GetSize()
    print('Number of cameras detected:', num_cameras)

    # TODO: Add something to setup GUI to select from multiple cameras? Or separate GUI?
    # Finish if there are no cameras
    if num_cameras == 0:
        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        input('Done! Press Enter to exit...')
        return False

    if num_cameras > 1:
        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Too many cameras!')
        input('Done! Press Enter to exit...')
        return False

    # Run example on each camera
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)

        result &= run_single_camera(cam, file_name)
        print('Camera %d example complete... \n' % i)

    # Release reference to camera
    del cam

    # Clear camera list before releasing system
    cam_list.Clear()

    # Release instance
    system.ReleaseInstance()

    input('Done! Press Enter to exit...')
    return result

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)