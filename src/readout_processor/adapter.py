from odin_control.adapters.adapter import ApiAdapter

from .controller import ReadoutProcessorController, ReadoutProcessorError


class ReadoutProcessorAdapter(ApiAdapter):
    """READOUTPROCESSOR Adapter class inheriting base adapter functionality."""

    controller_cls = ReadoutProcessorController
    error_cls = ReadoutProcessorError
