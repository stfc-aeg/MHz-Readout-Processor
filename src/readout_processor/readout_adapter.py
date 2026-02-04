from .readout_controller import ReadoutProcessorController, ReadoutProcessorError
from RegisterAccessor.base.base_adapter import BaseAdapter

class ReadoutProcessorAdapter(BaseAdapter):
    """READOUTPROCESSOR Adapter class inheriting base adapter functionality."""

    controller_cls = ReadoutProcessorController
    error_cls = ReadoutProcessorError