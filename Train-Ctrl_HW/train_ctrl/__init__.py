"""HW Train Controller: control law, fleet and Qt bridge.

Importing the package does not import Qt. The Qt modules,
train_ctrl.backend and train_ctrl.app, have to be imported by name.
"""

from .constants import *  # noqa: F401,F403
from .control import ControllerCore
from .errors import (DuplicateTrainError, InvalidInputError,
                     TrainControllerError, UnknownTrainError)
from .fleet import TrainControllerFleet
from .inputs import EVERY_TICK, read_inputs
from .state import State, TrainModelCommands
from .units import KMH_PER_MPS, MPS_TO_MPH, W_TO_KW, c_to_f, f_to_c