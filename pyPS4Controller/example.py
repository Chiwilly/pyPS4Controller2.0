from controller import Controller  # type: ignore
from time import sleep


# Create a controller
controller = Controller("/dev/input/js0")
controller.start_listening()
# Get the current state:
print(controller.get_current_state())
# Use the generator to get updates as they come:
# add try except block to break out of the loop
try:
    for state in controller.state_updates():
        sleep(0.05)
        print("Current Controller State\n ", state['x_button'], state['circle_button'])
except KeyboardInterrupt:
    controller.stop_listening()