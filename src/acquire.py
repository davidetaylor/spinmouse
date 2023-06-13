import PySpin
from collections import deque
import threading
import cv2
import csv
import time
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
from time import perf_counter


class waitAnimation:
    """
    A simple class that creates a rotating animation to display during a long-running process.

    Attributes:
        message (str): The message to display along with the animation.
        animation (str): The set of characters to use in the animation.
        idx (int): The current index of the animation character being displayed.

    Methods:
        print(): Prints the message and the current animation character, updating the display in place using
                 the '\r' character. Each call to print() updates the animation to the next character in the set.
    """
    def __init__(self, message):
        self.message = message
        self.animation = "|/-\\"
        self.idx = 0

    def print(self):
        """Prints the message and the current animation character

        Updates the display in place using the '\r' character.
        Each call to print() updates the animation to the next character in the set.
        """
        print(
            self.message + " {}".format(self.animation[self.idx % len(self.animation)]) + " "*20,
            end="\r",
        )
        self.idx += 1


class FrameCounter:
    """
    Tracks acquired, buffered, and dropped frames
    """

    def __init__(self):
        self.acquired = 0
        self.buffered = 0
        self.dropped = 0

        self.last_frameid = None

    def update(self, image_queue_length: int, frameid: int):
        '''
        Updates acquired, buffered, and dropped frame counters.
        Must be called every time a frame is saved

        To calculate number of dropped frames, compares the frame IDs for
        images the last two images saved and adds the difference to the counter.

        Args:
            image_queue_length (int): Number of images currently in queue
            frameid (int): Frame ID for most recent image
        '''
        self.acquired += 1
        self.buffered = image_queue_length

        if self.last_frameid is None:
            self.last_frameid = frameid
        else:
            self.dropped += frameid - self.last_frameid - 1
            self.last_frameid = frameid

    def print(self):
        # print current counter values in terminal
        acquired = str(self.acquired).rjust(12, " ")
        buffered = str(self.buffered).rjust(12, " ")
        dropped = str(self.dropped).rjust(12, " ")
        print(f"Acquired: {acquired}  |  Buffered: {buffered}  |  Dropped: {dropped}")


def acquire_images(acquisition_complete_event, images_queue, camera_system, config, camera_trigger_mode=False):
    """
    Attempts to grab images from camera stream until stop event is set

    Args:
        acquisition_complete_event (threading.Event): When set, signals acquisition loop should stop
        images_queue (collections.deque): Threadsafe image buffer
        camera_system (CameraSystem) Reference to CameraSystem object
        config (Config): Reference to Config object

    Returns:
        bool: True, if successful. False otherwise.
    """

    waiting_message = waitAnimation("Waiting for images from camera...(press 'Ctrl-C' to end)")
    receiving_message = waitAnimation("Receiving images from camera...(press 'Ctrl-C' to end)")

    if camera_trigger_mode:
        camera_system.camera.enable_trigger_mode()
    else:
        camera_system.camera.disable_trigger_mode()

    try:
        result = True

        camera_system.camera.begin_acquisition()

        while acquisition_complete_event.is_set() is False:
            """
            PySpin.SpinnakerException is thrown when "GetNextImage" times out,
            which is expected when camera is not sending images.

            This should not be treated as an error. Instead, use "continue" to
            bypass the rest of the code in the loop and try again.

            Note: if you don't provide a grabTimeout value the function will block
            indefinitely until the camera sends an image.
            """
            try:
                image_result = camera_system.camera.cam.GetNextImage(50)

            except PySpin.SpinnakerException:
                if acquisition_complete_event.is_set() is False:
                    waiting_message.print()
                continue

            if image_result.IsIncomplete():
                print("Image incomplete with image status %d..." % image_result.GetImageStatus())

            else:
                # put images in threadsafe collection.deque
                images_queue.append(image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR))

                # all images need to be released before acquisition ends
                image_result.Release()

            receiving_message.print()

        camera_system.camera.end_acquisition()

    except PySpin.SpinnakerException as ex:
        print("Error: %s" % ex)
        result = False

    return result


def get_id_timestamp_from_chunk_data(image):
    """Extracts FrameID and Timestamp from image chunk data.
    
    Args:
        image (PySpin.ImagePtr): Image grabbed from a PySpin.CameraPtr.
    """
    try:
        chunk_data = image.GetChunkData()

        frame_id = chunk_data.GetFrameID()
        timestamp = chunk_data.GetTimestamp()

    except PySpin.SpinnakerException as ex:
        print("Error: %s" % ex)

    return frame_id, timestamp


def save_images(acquisition_complete_event, images_queue, camera_system, config, display_image_queue=None):
    """
    Saves camera images to AVI and timestamps to CSV

    Args:
        acquisition_complete_event (threading.Event): When set, signals acquisition loop should stop
        images_queue (collections.deque): Threadsafe image buffer
        camera_system (CameraSystem) Reference to CameraSystem object
        config (Config): Reference to Config object
        display_image_queue (collections.deque, optional): A thread-safe image buffer to share images with GUIs

    Returns:
        bool: True, if successful. False otherwise.
    """

    video_file_path = config.parameters['file_path'] + ".avi"
    timestamps_file_path = config.parameters['file_path'] + "_timestamps.csv"

    video_save_framerate = config.parameters['video_save_framerate']

    try:
        result = True

        # get image height/width
        nodemap = camera_system.camera.cam.GetNodeMap()
        image_height = PySpin.CIntegerPtr(nodemap.GetNode("Height")).GetValue()
        image_width = PySpin.CIntegerPtr(nodemap.GetNode("Width")).GetValue()

        # TODO: use context managers for video and csv writers

        # open AVI with unique filename
        frame_size = (image_width, image_height)
        video_recorder = cv2.VideoWriter(
            video_file_path,
            cv2.CAP_FFMPEG,
            cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            video_save_framerate,
            frame_size,
            0,
        )

        # open log csv
        logfile = open(timestamps_file_path, "w", newline="")
        log_writer = csv.writer(logfile)

        # initialize frame counter
        frame_counter = FrameCounter()

        # Video/timestamp saving loop
        while True:
            if len(images_queue) > 0:

                # save image
                new_image = images_queue.popleft()
                video_recorder.write(new_image.GetNDArray())

                # save frame ID and timestamp
                frame_id, timestamp = get_id_timestamp_from_chunk_data(new_image)
                log_writer.writerow((frame_id, timestamp))

                # update frame counter
                frame_counter.update(len(images_queue), frame_id)

                # share data with gui
                if display_image_queue is None:
                    # print frame counters if there is no GUI 
                    if frame_counter.acquired % 100 == 0:
                        frame_counter.print()
                    pass
                else:
                    display_image_queue.append({
                        'image': new_image.GetNDArray(),
                        'acquired_counter': frame_counter.acquired,
                        'buffered_counter': frame_counter.buffered,
                        'dropped_counter': frame_counter.dropped
                        })

            else:
                time.sleep(0.01)
                if acquisition_complete_event.is_set():
                    break

        # Close log file
        logfile.close()

        # Close AVI file
        video_recorder.release()

        print(f'\nSaved frames: {frame_counter.acquired}  |  Dropped frames: {frame_counter.dropped}')
        print(f"Saved to {config.parameters['data_directory']}")

    except PySpin.SpinnakerException as ex:
        print("Error: %s" % ex)
        return False

    return result


class AcquireGui:
    """A tkinter GUI for displaying video and frame counts during acquisition
    
    """
    def __init__(self, acquisition_complete_event, display_image_queue, camera_system):
        """
        Args:
            acquisition_complete_event (threading.Event): When set, signals when all thread should stop
            display_image_queue (collections.deque): Threadsafe data buffer
            camera_system (CameraSystem) Reference to CameraSystem object
        """
        self.acquisition_complete_event = acquisition_complete_event
        self.display_image_queue = display_image_queue
        self.camera_system = camera_system

        self.gui = tk.Tk()
        self.gui.title("SpinMouse: Acquisition")

        # create basic GUI structure
        self.video_frame = tk.Frame(self.gui, width=650, height=400, bg='grey')
        self.video_frame.grid(row=0, column=0, padx=10, pady=5)
        self.controls_frame = tk.Frame(self.gui, width=400, height=400, bg='grey')
        self.controls_frame.grid(row=0, column=1, padx=10, pady=5)

        # Create video
        self.video = tk.Label(self.video_frame)
        self.video.grid(row=0, column=0)

        # temporay placeholder for the video feed
        img = Image.fromarray(np.zeros((200, 300)))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video.image = imgtk
        self.video.configure(image=imgtk)

        # initialize frame counters
        self.acquired_frame_counter_val = tk.StringVar()
        self.acquired_frame_counter_val.set(str(0))
        self.acquired_frame_counter_caption = tk.Label(self.controls_frame, text='Acquired frames:').grid(row=0, column=0, padx=5, pady=5)
        self.acquired_frame_counter_display = tk.Label(self.controls_frame, textvariable=self.acquired_frame_counter_val).grid(row=0, column=1, padx=5, pady=5)

        self.buffered_frame_counter_val = tk.StringVar()
        self.buffered_frame_counter_val.set(str(0))
        self.buffered_frame_counter_caption = tk.Label(self.controls_frame, text='Buffered frames:').grid(row=1, column=0, padx=5, pady=5)
        self.buffered_frame_counter_display = tk.Label(self.controls_frame, textvariable=self.buffered_frame_counter_val).grid(row=1, column=1, padx=5, pady=5)

        self.dropped_frame_counter_val = tk.StringVar()
        self.dropped_frame_counter_val.set(str(0))
        self.dropped_frame_counter_caption = tk.Label(self.controls_frame, text='Dropped frames:').grid(row=2, column=0, padx=5, pady=5)
        self.dropped_frame_counter_display = tk.Label(self.controls_frame, textvariable=self.dropped_frame_counter_val).grid(row=2, column=1, padx=5, pady=5)

        # initialize toggle for trigger mode
        self.trigger_mode_checkbutton_value = tk.BooleanVar()
        self.trigger_mode_checkbutton_value.set(True)
        self.trigger_mode_checkbutton = tk.Checkbutton(
                                                            self.controls_frame,
                                                            text='Trigger Mode',
                                                            command=self.toggle_trigger_mode,
                                                            variable=self.trigger_mode_checkbutton_value,
                                                            onvalue=True,
                                                            offvalue=False,
                                                            )
        self.trigger_mode_checkbutton.grid(row=3, column=0, columnspan = 2, padx=5, pady=5)

        self.stop_acquisition_button = tk.Button(self.controls_frame, text='Stop Acquisition', command=self.close_gui, bg='red').grid(row=4, column=0, columnspan = 2, padx=5, pady=5)

        # Cleanup on closing
        self.gui.protocol("WM_DELETE_WINDOW", self.close_gui)

    def close_gui(self):
        self.acquisition_complete_event.set()
        self.gui.destroy()

    def toggle_trigger_mode(self):
        if self.trigger_mode_checkbutton_value.get() is True:
            self.camera_system.camera.enable_trigger_mode()
        else:
            self.camera_system.camera.disable_trigger_mode()

    def update_video(self):
        """Update video image, if possible."""
        if len(self.display_image_queue) > 0:
            display_data = self.display_image_queue.popleft()

            # update image
            img = Image.fromarray(display_data['image'])
            imgtk = ImageTk.PhotoImage(image = img)
            self.video.configure(image=imgtk)
            self.video.image = imgtk

            # update counters
            self.acquired_frame_counter_val.set(str(display_data['acquired_counter']))
            self.buffered_frame_counter_val.set(str(display_data['buffered_counter']))
            self.dropped_frame_counter_val.set(str(display_data['dropped_counter']))

        # This creates a feedback loop causing "update_video" to be called at a fixed interval
        # limiting update framerate to 50Hz for performance
        self.gui.after(20, self.update_video)


def acquisition_gui(acquisition_complete_event, display_image_queue, camera_system):
    """Starts instance of AcquireGui

    Args:
        acquisition_complete_event (threading.Event): When set, signals acquisition loop should stop
        display_image_queue (collections.deque, optional): A thread-safe queue to share data with GUIs
        camera_system (CameraSystem) Reference to CameraSystem object
    """
    acquire_gui = AcquireGui(acquisition_complete_event, display_image_queue, camera_system)
    acquire_gui.update_video()
    acquire_gui.gui.mainloop()


def run_experiment_gui(camera_system, config):
    """Acquire and save video. Display video feed and frame counters in GUI

    This version of "run_experiment" may run slower because of the GUI. If you
    are having lots of dropped frames, "run_experiment_cli" may perform better.

    Use the config file to select which version of "run_experiment" to use.

    Args:
        camera_system (CameraSystem): Reference to CameraSystem object
        config (Config): Reference to Config object

    This function starts three threads: one for acquiring images from the camera,
    one for saving the acquired images to disk, and one for displaying the video
    feed and frame counters in a GUI.

    It uses a deque as a threadsafe image buffer, and a threading.Event to
    signal when acquisition is complete.
    """
    if camera_system.camera.enable_chunk_data() is False:
        print("Unable to enable chunk data")

    # infinitely large threadsafe image buffer
    images_queue = deque([])

    # thread-safe queue to share data with GUIs
    display_image_queue = deque([], maxlen=1)

    # Create an thread event to signal when acquisition is complete
    acquisition_complete_event = threading.Event()

    # Create threads for acquiring and saving images
    acquire_images_thread = threading.Thread(
        target=acquire_images,
        args=[acquisition_complete_event, images_queue, camera_system, config],
        kwargs={'camera_trigger_mode':True}
    )
    save_images_thread = threading.Thread(
        target=save_images,
        args=[acquisition_complete_event, images_queue, camera_system, config],
        kwargs={'display_image_queue':display_image_queue}
    )
    acquisition_gui_thread = threading.Thread(
        target=acquisition_gui,
        args=[acquisition_complete_event, display_image_queue, camera_system],
    )
    acquire_images_thread.start()
    save_images_thread.start()
    acquisition_gui_thread.start()

    # close threads gracefully
    while acquire_images_thread.is_alive() or save_images_thread.is_alive() or acquisition_gui_thread.is_alive():
        try:
            if acquire_images_thread.is_alive():
                acquire_images_thread.join(0.5)

            if save_images_thread.is_alive():
                save_images_thread.join(0.5)

            if acquisition_gui_thread.is_alive():
                acquisition_gui_thread.join(0.5)

        except KeyboardInterrupt:
            acquisition_complete_event.set()
            print("\n\n'Ctrl-C' pressed: stopping experiment...")

    if camera_system.camera.disable_chunk_data() is False:
        print("Unable to disable chunk data")


def run_experiment_cli(camera_system, config):
    """Acquire and save video. Display frame counters in terminal.

    In theory, this version of "run_experiment" may perform better
    because it does not have the overhead of the GUI.

    Use the config file to select which version of "run_experiment" to use.

    Args:
        camera_system (CameraSystem): Reference to CameraSystem object
        config (Config): Reference to Config object

    This function starts two threads: one for acquiring images from the camera
    and one for saving the acquired images to disk.

    It uses a deque as a threadsafe image buffer, and a threading.Event to
    signal when acquisition is complete.
    """

    if camera_system.camera.enable_chunk_data() is False:
        print("Unable to enable chunk data")

    # infinitely large threadsafe image buffer
    images_queue = deque([])

    # Create an thread event to signal when acquisition is complete
    acquisition_complete_event = threading.Event()

    # Create threads for acquiring and saving images
    acquire_images_thread = threading.Thread(
        target=acquire_images,
        args=[acquisition_complete_event, images_queue, camera_system, config],
        kwargs={'camera_trigger_mode':True}
    )
    save_images_thread = threading.Thread(
        target=save_images,
        args=[acquisition_complete_event, images_queue, camera_system, config],
    )

    acquire_images_thread.start()
    save_images_thread.start()

    # close threads gracefully
    while acquire_images_thread.is_alive() or save_images_thread.is_alive():
        try:
            if acquire_images_thread.is_alive():
                acquire_images_thread.join(0.5)

            if save_images_thread.is_alive():
                save_images_thread.join(0.5)

        except KeyboardInterrupt:
            acquisition_complete_event.set()
            print("\n\n'Ctrl-C' pressed: stopping experiment...")

    if camera_system.camera.disable_chunk_data() is False:
        print("Unable to disable chunk data")
