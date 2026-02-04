import logging
from odin.adapters.parameter_tree import ParameterTree, ParameterTreeError
from RegisterAccessor.controller import RegisterAccessorController, ControllerError
from RegisterAccessor.RegisterMap import RegisterMap, RegisterMapError

class ReadoutProcessorError(ControllerError):
    """Simple exception class to wrap lower-level exceptions."""


class ReadoutProcessorController(RegisterAccessorController):
    """Controller class for READOUTPROCESSOR."""

    def __init__(self, options):
        super().__init__(options)
        

    def initialize(self, adapters):
        self.adapters = adapters
        logging.debug(f"Adapters initialized: {list(adapters.keys())}")
        # Add to param tree if needed post-initialization

    def cleanup(self):
        logging.info("Cleaning up ReadoutProcessorController")

    def get(self, path, with_metadata=False):
        try:
            return self.param_tree.get(path, with_metadata)
        except ParameterTreeError as error:
            logging.error(error)
            raise ReadoutProcessorError(error)

    def set(self, path, data):
        try:
            self.param_tree.set(path, data)
        except ParameterTreeError as error:
            logging.error(error)
            raise ReadoutProcessorError(error)