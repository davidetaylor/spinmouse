import os
import tkinter as tk
from PIL import Image, ImageTk
import traceback
import threading
from collections import deque
from datetime import date
from src.acquire import acquire_images


class SetupGUI:
    """A tkinter GUI for setting up experiment.
    
    - Shows a live video feed from camera
    - Change image offset by clicking on the video feed
    - Enter experiment ID for use in filename

    Attributes:
        continue_experiment (bool): True, if user selects the "Begin Acquisition" button. False, otherwise.
        default_experiment_id (str): Default experiment name to pre-populate GUI
    """
    def __init__(self, acquisition_complete_event, images_queue, camera_system, config):
        """
        Args:
            acquisition_complete_event (threading.Event): When set, signals when all thread should stop
            images_queue (collections.deque): Threadsafe image buffer
            camera_system (CameraSystem) Reference to CameraSystem object
            config (Config): Reference to Config object
        """
        self.acquisition_complete_event = acquisition_complete_event
        self.images_queue = images_queue
        self.camera_system = camera_system
        self.config = config

        self.continue_experiment = False
        self.default_experiment_id = "{date}_01_".format(date=date.today().strftime("%Y%m%d"))

        # initialize GUI components
        self.gui = tk.Tk()
        self.gui.title("SpinMouse Setup")

        # create basic GUI structure
        self.gui_vid_frame = tk.Frame(self.gui, width=700, height=700, bg='grey')
        self.gui_vid_frame.grid(row=0, column=0, padx=10, pady=10)
        self.gui_controls_frame = tk.Frame(self.gui, width=400, height=700, bg='grey')
        self.gui_controls_frame.grid(row=0, column=1, padx=10, pady=10)

        # Create video
        self.gui_vid = tk.Label(self.gui_vid_frame)
        self.gui_vid.grid(row=0, column=0)
        self.gui_vid.bind('<Button-1>', self.mouse_click_callback)

        # instructions
        self.gui_instructions_label = tk.Label(
            self.gui_controls_frame,
            text='Click on the video feed to \nre-position the camera view'
            )
        self.gui_instructions_label.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # experiment naming
        self.gui_experiment_id_value = tk.StringVar()
        self.gui_experiment_id_value.set(self.default_experiment_id)

        self.gui_experiment_id_label = tk.Label(self.gui_controls_frame, text='Experiment ID:')
        self.gui_experiment_id_label.grid(row=2, column=0, padx=5, pady=5)

        self.gui_experiment_id_entry = tk.Entry(self.gui_controls_frame, textvariable=self.gui_experiment_id_value)
        self.gui_experiment_id_entry.grid(row=2, column=1, padx=5, pady=5)
        self.gui_experiment_id_entry.focus_set()
        self.gui_experiment_id_entry.icursor(len(self.gui_experiment_id_entry.get()))  # moves cursor to end of line

        # Exit buttons
        self.gui_cancel_experiment_button = tk.Button(
            self.gui_controls_frame,
            text='Cancel',
            command=self.cancel_experiment_callback,
            bg='orange',
            )
        self.gui_cancel_experiment_button.grid(row=3, column=0, columnspan=1, padx=5, pady=5)

        self.gui_begin_experiment_button = tk.Button(
            self.gui_controls_frame,
            text='Begin Experiment',
            command=self.begin_experiment_callback,
            bg='green',
            )
        self.gui_begin_experiment_button.grid(row=3, column=1, columnspan=1, padx=5, pady=5)

        # cleanup if window is closed
        self.gui.protocol("WM_DELETE_WINDOW", self.cancel_experiment_callback)

    def cancel_experiment_callback(self):
        self.continue_experiment = False
        self.close_gui()

    def begin_experiment_callback(self):
        self.continue_experiment = True
        self.close_gui()

    def close_gui(self):
        self.get_user_input()
        self.acquisition_complete_event.set()
        self.gui.destroy()

    def get_user_input(self):
        # Collects input from entries and saves to config.parameters (dict)
        self.config.parameters['experiment_id'] = self.gui_experiment_id_entry.get()

    def mouse_click_callback(self, event):
        """
        Requests that the camera system adjust image offset

        event.x and event.y are the x,y coordinates within the video frame
        """
        offsetx_delta = event.x - self.gui_vid.image.width()/2
        offsety_delta = event.y - self.gui_vid.image.height()/2

        self.camera_system.camera.update_image_offset(offsetx_delta, offsety_delta)

    def update_video(self):
        """Update video image, if possible."""
        if len(self.images_queue) > 0:
            new_image = self.images_queue.popleft()
            img = Image.fromarray(new_image.GetNDArray())
            imgtk = ImageTk.PhotoImage(image=img)
            self.gui_vid.configure(image=imgtk)
            self.gui_vid.image = imgtk  # To prevent garbage collection of imgtk

        # This creates a feedback loop causing "update_video" to be called at a fixed interval
        self.gui.after(5, self.update_video)


def setup_experiment(camera_system, config):
    """Run setup GUI to show live video feed and provide user input

    Args:
        camera_system (CameraSystem): Reference to CameraSystem object
        config (Config): Reference to Config object

    Returns:
        bool: True, if successful. False otherwise.
    """
    result = True

    # threadsafe image buffer and stop event
    images_queue = deque(maxlen=10)
    acquisition_complete_event = threading.Event()

    # Create thread for acquiring images
    acquire_images_thread = threading.Thread(
        target=acquire_images,
        args=[acquisition_complete_event, images_queue, camera_system, config],
        kwargs={'camera_trigger_mode':False}
    )
    acquire_images_thread.start()

    # Start setup GUI
    setup_gui = SetupGUI(acquisition_complete_event, images_queue, camera_system, config)
    setup_gui.update_video()
    setup_gui.gui.mainloop()
    result &= setup_gui.continue_experiment

    acquire_images_thread.join()

    config.parameters['file_path'] = os.path.join(
        config.parameters["data_directory"],
        config.parameters['experiment_id'] + "_" + config.parameters["filename_suffix"]
        )

    return result
