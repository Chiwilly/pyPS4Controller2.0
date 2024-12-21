import struct
from os import path
from time import sleep
import threading
from typing import Optional
from queue import Queue, Empty

class ControllerState:
    """
    Represents the current state of the PS4 controller.
    """
    def __init__(self) -> None:
        self.x_button: bool = False
        self.triangle_button: bool = False
        self.circle_button: bool = False
        self.square_button: bool = False

        self.L1_button: bool = False
        self.L2_button: int = -32767
        self.L3_button: bool = False

        self.R1_button: bool = False
        self.R2_button: int = -32767
        self.R3_button: bool = False

        self.up_arrow: bool = False
        self.down_arrow: bool = False
        self.left_arrow: bool = False
        self.right_arrow: bool = False

        self.L3_x_axis: int = 0
        self.L3_y_axis: int = 0

        self.R3_x_axis: int = 0
        self.R3_y_axis: int = 0

        self.share_button: bool = False
        self.options_button: bool = False
        self.playstation_button: bool = False

    def to_dict(self) -> dict:
        return {
            'x_button': self.x_button,
            'triangle_button': self.triangle_button,
            'circle_button': self.circle_button,
            'square_button': self.square_button,
            'L1_button': self.L1_button,
            'L2_button': self.L2_button,
            'L3_button': self.L3_button,
            'R1_button': self.R1_button,
            'R2_button': self.R2_button,
            'R3_button': self.R3_button,
            'up_arrow': self.up_arrow,
            'down_arrow': self.down_arrow,
            'left_arrow': self.left_arrow,
            'right_arrow': self.right_arrow,
            'L3_x_axis': self.L3_x_axis,
            'L3_y_axis': self.L3_y_axis,
            'R3_x_axis': self.R3_x_axis,
            'R3_y_axis': self.R3_y_axis,
            'share_button': self.share_button,
            'options_button': self.options_button,
            'playstation_button': self.playstation_button
        }

class Controller:
    def __init__(self, interface: str, event_format: str = "3Bh2b", event_definition=None) -> None:
        """
        Initialize the controller instance.
        :param interface: Path to the device interface (e.g., /dev/input/js0).
        :param event_format: The struct format to unpack the events.
        :param event_definition: A callable class or function that maps button_id, button_type, and value 
                                 to specific events. If None, uses a default mapping.
        """
        self.stop = False
        self.is_connected = False
        self.interface = interface
        self.debug = False
        self.event_format = event_format

        # Default mapping if none provided
        if event_definition is None:
            from event_mapping.Mapping3Bh2b import Mapping3Bh2b  # type: ignore
            self.event_definition = Mapping3Bh2b
        else:
            self.event_definition = event_definition

        self.event_size = struct.calcsize(self.event_format)
        self.event_history: list = []
        self.state = ControllerState()

        # Queue to notify about new state updates
        self._state_queue: Queue = Queue()
        self._listening_thread: Optional[threading.Thread] = None

    def start_listening(self, timeout=30):
        """
        Start the event reading in a separate thread.
        """
        self.stop = False
        self._listening_thread = threading.Thread(
            target=self.listen,
            args=(timeout,),
            daemon=True
        )
        self._listening_thread.start()

    def stop_listening(self):
        """
        Stop listening and join the thread.
        """
        self.stop = True
        if self._listening_thread is not None:
            self._listening_thread.join()

    def get_current_state(self):
        """
        Returns the current state as a dictionary.
        """
        return self.state.to_dict()

    def state_updates(self):
        """
        A generator that yields the latest state whenever it is updated.
        """
        while not self.stop:
            try:
                self._state_queue.get(timeout=1)
                yield self.get_current_state()
            except Empty:
                continue

    def listen(self, timeout=30):
        """
        Listen for events on the interface.
        :param timeout: How long to wait for the interface before giving up.
        """
        def on_connect_callback():
            self.is_connected = True

        def on_disconnect_callback():
            self.is_connected = False

        def wait_for_interface():
            for _ in range(timeout):
                if path.exists(self.interface):
                    on_connect_callback()
                    return True
                sleep(1)
            on_disconnect_callback()
            return False

        if not wait_for_interface():
            return

        try:
            with open(self.interface, "rb") as _file:
                event = _file.read(self.event_size)
                while not self.stop and event:
                    (overflow, value, button_type, button_id) = self._unpack_event(event)
                    self._handle_event(button_id, button_type, value, overflow)
                    self._state_queue.put(True)
                    event = _file.read(self.event_size)

        except KeyboardInterrupt:
            on_disconnect_callback()
            self.stop_listening()

    def _unpack_event(self, event):
        __event = struct.unpack(self.event_format, event)
        # event_definition uses a certain ordering
        return (__event[3:], __event[2], __event[1], __event[0])

    def _handle_event(self, button_id, button_type, value, overflow):

        event = self.event_definition(
            button_id=button_id,
            button_type=button_type,
            value=value,
            connecting_using_ds4drv=False,  # ds4drv not used, set False
            overflow=overflow,
            debug=self.debug
        )

        # Update state based on event
        # Add similar logic for all events you want to track.
        # Below is an example set - you need to adapt to your event_definition's logic.
        if event.R3_event():
            self.event_history.append("right_joystick")
            if event.R3_y_at_rest():
                self.state.R3_y_axis = 0
            elif event.R3_x_at_rest():
                self.state.R3_x_axis = 0
            elif event.R3_right():
                self.state.R3_x_axis = event.value
            elif event.R3_left():
                self.state.R3_x_axis = event.value
            elif event.R3_up():
                self.state.R3_y_axis = event.value
            elif event.R3_down():
                self.state.R3_y_axis = event.value

        elif event.L3_event():
            self.event_history.append("left_joystick")
            if event.L3_y_at_rest():
                self.state.L3_y_axis = 0
            elif event.L3_x_at_rest():
                self.state.L3_x_axis = 0
            elif event.L3_up():
                self.state.L3_y_axis = event.value
            elif event.L3_down():
                self.state.L3_y_axis = event.value
            elif event.L3_left():
                self.state.L3_x_axis = event.value
            elif event.L3_right():
                self.state.L3_x_axis = event.value

        elif event.circle_pressed():
            self.event_history.append("circle")
            self.state.circle_button = True
        elif event.circle_released():
            self.state.circle_button = False

        elif event.x_pressed():
            self.event_history.append("x")
            self.state.x_button = True
        elif event.x_released():
            self.state.x_button = False

        elif event.triangle_pressed():
            self.event_history.append("triangle")
            self.state.triangle_button = True
        elif event.triangle_released():
            self.state.triangle_button = False

        elif event.square_pressed():
            self.event_history.append("square")
            self.state.square_button = True
        elif event.square_released():
            self.state.square_button = False

        elif event.L1_pressed():
            self.event_history.append("L1")
            self.state.L1_button = True
        elif event.L1_released():
            self.state.L1_button = False

        elif event.L2_pressed():
            self.event_history.append("L2")
            self.state.L2_button = event.value
        elif event.L2_released():
            self.state.L2_button = -32767

        elif event.R1_pressed():
            self.event_history.append("R1")
            self.state.R1_button = True
        elif event.R1_released():
            self.state.R1_button = False

        elif event.R2_pressed():
            self.event_history.append("R2")
            self.state.R2_button = event.value
        elif event.R2_released():
            self.state.R2_button = -32767

        elif event.options_pressed():
            self.event_history.append("options")
            self.state.options_button = True
        elif event.options_released():
            self.state.options_button = False

        elif event.left_right_arrow_released():
            self.state.left_arrow = False
            self.state.right_arrow = False

        elif event.up_down_arrow_released():
            self.state.up_arrow = False
            self.state.down_arrow = False

        elif event.left_arrow_pressed():
            self.event_history.append("left")
            self.state.left_arrow = True

        elif event.right_arrow_pressed():
            self.event_history.append("right")
            self.state.right_arrow = True

        elif event.up_arrow_pressed():
            self.event_history.append("up")
            self.state.up_arrow = True

        elif event.down_arrow_pressed():
            self.event_history.append("down")
            self.state.down_arrow = True

        elif event.playstation_button_pressed():
            self.event_history.append("ps")
            self.state.playstation_button = True
        elif event.playstation_button_released():
            self.state.playstation_button = False

        elif event.share_pressed():
            self.event_history.append("share")
            self.state.share_button = True
        elif event.share_released():
            self.state.share_button = False

        elif event.R3_pressed():
            self.event_history.append("R3")
            self.state.R3_button = True
        elif event.R3_released():
            self.state.R3_button = False

        elif event.L3_pressed():
            self.event_history.append("L3")
            self.state.L3_button = True
        elif event.L3_released():
            self.state.L3_button = False
