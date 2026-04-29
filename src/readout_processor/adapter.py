from RegisterAccessor.base.base_adapter import BaseAdapter

from .controller import ReadoutProcessorController, ReadoutProcessorError


class ReadoutProcessorAdapter(BaseAdapter):
    """READOUTPROCESSOR Adapter class inheriting base adapter functionality."""

    controller_cls = ReadoutProcessorController
    error_cls = ReadoutProcessorError
