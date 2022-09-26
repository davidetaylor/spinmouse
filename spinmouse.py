# -*- coding: utf-8 -*-
import PySpin
import sys
import os
import csv
import time
import keyboard
import threading
import queue
from collections import deque
import cv2
import numpy as np


AVI_SAVE_FRAME_RATE = 100 # this only affects the frame rate of the video, not the acquisition


def save_images(acquisition_complete_event, file_name, images_queue):
    """
    This function prepares, saves, and cleans up an AVI video from a vector of images.
    Uses OpenCV + FFMPEG to save video

    :param images: List of images to save to an AVI video.
    :type images: list of ImagePtr
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    try:
        result = True

        # open AVI with unique filename
        frame_size = (336, 300)
        video_recorder = cv2.VideoWriter(file_name+"001.avi", cv2.CAP_FFMPEG, cv2.VideoWriter_fourcc('M','J','P','G'), 100.0, frame_size, 0)

        # Construct and save AVI video
        print('Appending images to AVI file')

        while True:
            try:
                # new_image = images_queue.get(block=False)
                new_image = images_queue.popleft()
                start_time = time.time()
                video_recorder.write(new_image.GetNDArray())
                print("It took", time.time() - start_time, "to to save frame")
                print('Image appended')
            # except queue.Empty:
            except IndexError:
                if acquisition_complete_event.is_set():
                    break
                print('Consumer: got nothing, waiting a while...')
                time.sleep(0.5)
                continue

        # Close AVI file
        video_recorder.release()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result

# def save_images(acquisition_complete_event, file_name, images_queue):
#     """
#     This function prepares, saves, and cleans up an AVI video from a vector of images.
#     Uses Spinnaker SpinVideo to save video

#     :param images: List of images to save to an AVI video.
#     :type images: list of ImagePtr
#     :return: True if successful, False otherwise.
#     :rtype: bool
#     """

#     try:
#         result = True

#         avi_filename = file_name
#         framerate_to_set = AVI_SAVE_FRAME_RATE

#         # open AVI with unique filename

#         avi_recorder = PySpin.SpinVideo()

#         option = PySpin.H264Option()
#         option.frameRate = framerate_to_set
#         option.bitrate = 1000000
#         option.height = 300
#         option.width = 336

#         option = PySpin.MJPGOption()
#         option.frameRate = framerate_to_set
#         option.quality = 75
#         option.height = 300
#         option.width = 336 

#         avi_recorder.Open(avi_filename, option)

#         # Construct and save AVI video
#         print('Appending images to AVI file')

#         while True:
#             try:

#                 # new_image = images_queue.get(block=False)
#                 new_image = images_queue.popleft()
#                 start_time = time.time()
#                 avi_recorder.Append(new_image)
#                 print("It took", time.time() - start_time, "to to save frame")
#                 print('Image appended')
#             # except queue.Empty:
#             except IndexError:
#                 if acquisition_complete_event.is_set():
#                     break
#                 print('Consumer: got nothing, waiting a while...')
#                 time.sleep(0.5)
#                 continue



#         # Close AVI file
#         avi_recorder.Close()
#         print('Video saved at %s.avi' % avi_filename)

#     except PySpin.SpinnakerException as ex:
#         print('Error: %s' % ex)
#         return False

#     return result





def acquire_images(acquisition_complete_event, cam, nodemap, images_queue):
    """

    :param cam: Camera to acquire images from.
    :param nodemap: Device nodemap.
    :type cam: CameraPtr
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
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

##        print('Enabling entries...')

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
##                print('{} enabled'.format(chunk_str))
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
        result = False

    return result




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

##        print('Disabling entries...')

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
##                print('{} disabled'.format(chunk_symbolic_form))
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

        # Retrieve GenICam nodemap
        nodemap = cam.GetNodeMap()

        # # Configure chunk data
        # if configure_chunk_data(nodemap) is False:
        #     return False

        # Create infinitely large image buffer queue
        # images_queue = queue.Queue(maxsize=0)
        images_queue = deque([])

        # Create an thread event to signal when acquisition is complete
        acquisition_complete_event = threading.Event()

        # Create threads for acquiring and saving images
        acquire_images_thread = threading.Thread(target=acquire_images, args=[acquisition_complete_event, cam, nodemap, images_queue])
        save_images_thread = threading.Thread(target=save_images, args=[acquisition_complete_event, file_name, images_queue])
        acquire_images_thread.start()
        save_images_thread.start()
        acquire_images_thread.join()
        save_images_thread.join()

        # # Disable chunk data
        # if disable_chunk_data(nodemap) is False:
        #     return False

        # Deinitialize camera
        cam.DeInit()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result



def main():
    """
    Example entry point; please see Enumeration example for more in-depth
    comments on preparing and cleaning up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """

    file_name = input("Enter filename (e.g., YYYYMMDD_##_IDNum): ")
    file_name = file_name + "_BodyCam"
    
    result = True

    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()

    num_cameras = cam_list.GetSize()

    print('Number of cameras detected:', num_cameras)

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