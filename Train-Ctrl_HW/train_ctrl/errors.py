"""Every error this module raises."""


class TrainControllerError(Exception):
    """Base class for every error this module raises."""


class InvalidInputError(TrainControllerError):
    """An input on the interface could not be read as its type."""


class DuplicateTrainError(TrainControllerError):
    """A train with that ID already has a controller."""


class UnknownTrainError(TrainControllerError, KeyError):
    """No train with that ID has a controller."""