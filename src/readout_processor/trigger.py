import logging
from dataclasses import dataclass
from functools import partial
from typing import Callable
from enum import IntEnum, Enum
from RegisterAccessor.RegisterMap import BitField, Register, RegisterMap
from contextlib import contextmanager


@dataclass
class TriggerRegisters:
    trigger: Register = None
    acq_limit_lower: Register = None
    acq_limit_upper: Register = None
    acq_current_lower: Register = None
    acq_current_upper: Register = None
    frames_per_tf: Register = None
    tf_per_trigger_lower: Register = None
    tf_per_trigger_upper: Register = None


@dataclass
class TriggerFields:
    trigger_mode: BitField = None
    trigger_resets_time_frame_en: BitField = None
    trigger_polarity: BitField = None
    software_histogram_trigger: BitField = None
    trigger_disable: BitField = None


class TriggerModes(IntEnum):
    STEP_SCAN = 0b00
    BURST_MODE = 0b01
    CONTINUOUS_MODE = 0b10


class TriggerPolarity(IntEnum):
    LEVEL_HIGH = 0b00
    LEVEL_LOW = 0b01
    RISING_EDGE = 0b10
    FALLING_EDGE = 0b11


class TriggerController:
    """Class to control the triggering options in the Readout Adapter"""

    TRIGGER_REGNAME_PREFIX = "hexitec_mhz_front_end_hexitec_hist_frame_generator"
    """All trigger reg's start with this in the name"""
    TRIGGER_REGS = {
        "trigger": "trigger_ctrl",
        "acq_limit_lower": "acq_window_flimit_lower",
        "acq_limit_upper": "acq_window_flimit_upper",
        "acq_current_lower": "acq_window_fcount_lower",
        "acq_current_upper": "acq_window_fcount_upper",
        "frames_per_tf": "sequence_count_flimit",
        "tf_per_trigger_lower": "histogram_count_flimit_lower",
        "tf_per_trigger_upper": "histogram_count_flimit_upper",

    }
    """Dict of regsiters for the Trigger Controls. will be prefixed with TRIGGER_REGNAME_PREFIX"""

    def __init__(
            self, regMap: RegisterMap,
            read_reg: Callable[[Register], int],
            write_reg: Callable[[int | bytes, Register], None],
            read_field: Callable[[Register, BitField], int],
            write_field: Callable[[int, Register, BitField], None]):

        try:
            self.registers = TriggerRegisters()
            for key, val in self.TRIGGER_REGS.items():
                regs = regMap.getReg("_".join([self.TRIGGER_REGNAME_PREFIX, val]))
                setattr(self.registers, key, next(regs))
        except StopIteration:
            logging.error("One of the required Trigger registers could not be found")

        try:
            self.trig_fields = TriggerFields()
            for bit in self.registers.trigger.bitFields:
                setattr(self.trig_fields, bit.name, bit)
        except StopIteration:
            logging.error("One of the Bitfields in the Trigger register could not be found")

        self.read_reg = read_reg
        self.write_reg = write_reg
        self.read_field = read_field
        self.write_field = write_field

        self.tree = {
            "enable": (self.get_enable, self.set_enable,
                       {"description": "Enable or disable triggering"}),
            "mode": (self.get_mode, self.set_mode,
                     {"allowed_values": [self.enumToString(val) for val in TriggerModes]}),
            "polarity": (self.get_polarity, self.set_polarity,
                         {"allowed_values": [self.enumToString(val) for val in TriggerPolarity]}),
            "reset_time_frame": (self.get_reset_tf, self.set_reset_tf,
                                 {"description": "Reset Timeframe on every trigger in Burst Mode"}),
            "debug_trigger": (None, lambda _: self.debug_trigger(),
                              {"description": "Send a single trigger via software, for testing"}),
            "acquisition_count": (
                partial(self.read_large_val,
                        self.registers.acq_current_lower,
                        self.registers.acq_current_upper
                        ),
                None,
                {"description": "Frames in current Acquisition. 48 Bits"}
            ),
            "frame_limits": {
                "acquisition": (
                    partial(self.read_large_val,
                            self.registers.acq_limit_lower, self.registers.acq_limit_upper
                            ),
                    partial(self.write_large_val,
                            self.registers.acq_limit_lower, self.registers.acq_limit_upper
                            ),
                    {"description": "Total number of frames desired for Acquisition. 48 Bits",
                     "max": 0xFFFFFFFFFFFF}
                ),
                "hist_in_trigger": (
                    partial(self.read_large_val,
                            self.registers.tf_per_trigger_lower,
                            self.registers.tf_per_trigger_upper),
                    partial(self.write_large_val,
                            self.registers.tf_per_trigger_lower,
                            self.registers.tf_per_trigger_upper),
                    {"description": "Histograms (Time Frames) per trigger in Burst Mode. 35 Bits",
                        "max": 0x7FFFFFFFF}
                ),
                "frame_in_hist": (
                    partial(self.read_reg, self.registers.frames_per_tf),
                    partial(self.write_reg, register=self.registers.frames_per_tf),
                    {
                        "description": "Frames per Histogram in Step Scan/Burst Mode. 32 Bits",
                        "max": 0xFFFFFFFF
                    }
                )
            }
        }

    def enumToString(self, enumVal: Enum) -> str:
        val_name = enumVal._name_
        return val_name.lower().replace("_", " ")

    def stringToEnum(self, enumStr: str) -> str:
        return enumStr.upper().replace(" ", "_")

    @contextmanager
    def disable_while_changing(self):
        """Ensure the trigger is disabled when chaning mode values"""
        enabled = self.get_enable()
        if enabled:
            self.set_enable(False)
        yield
        if enabled:
            self.set_enable(True)

    def get_enable(self) -> bool:
        """Get if Trigger is enabled. True of bitfield == 0"""
        return self.read_field(
            self.registers.trigger,
            self.trig_fields.trigger_disable) == 0

    def set_enable(self, enable: bool):
        return self.write_field(
            0 if enable else 1,
            self.registers.trigger,
            self.trig_fields.trigger_disable)

    def get_mode(self):
        val = self.read_field(self.registers.trigger,
                              self.trig_fields.trigger_mode)
        return self.enumToString(TriggerModes(val))

    def set_mode(self, mode: str):
        with self.disable_while_changing():
            field = self.trig_fields.trigger_mode
            val = TriggerModes[self.stringToEnum(mode)]
            self.write_field(val, self.registers.trigger, field)

    def get_polarity(self):
        val = self.read_field(self.registers.trigger,
                              self.trig_fields.trigger_polarity)
        return self.enumToString(TriggerPolarity(val))

    def set_polarity(self, polarity: str):
        with self.disable_while_changing():
            field = self.trig_fields.trigger_polarity
            val = TriggerPolarity[self.stringToEnum(polarity)]
            self.write_field(val, self.registers.trigger, field)

    def get_reset_tf(self):
        return self.read_field(
            self.registers.trigger,
            self.trig_fields.trigger_resets_time_frame_en) == 1

    def set_reset_tf(self, reset: bool):
        with self.disable_while_changing():
            field = self.trig_fields.trigger_resets_time_frame_en
            val = 1 if reset else 0
            self.write_field(val, self.registers.trigger, field)

    def debug_trigger(self):
        """Send a trigger via software, for testing.
        Triggers a single pulse in Rising Edge Mode, ignoring the polarity config"""
        field = self.trig_fields.software_histogram_trigger
        # assert bit low, then high, for a single trigger on the rising edge
        self.write_field(0, self.registers.trigger, field)
        self.write_field(1, self.registers.trigger, field)

    def read_large_val(self, lower: Register, upper: Register):
        """Read two registers to get a value that might not fit into a 32 bit number"""
        return self.read_reg(lower) | (self.read_reg(upper) << 32)

    def write_large_val(self, lower: Register, upper: Register, val: int):
        """Write a value that may be larger than 32 bits to two registers"""

        low_val = val & 0xFFFFFFFF
        up_val = (val >> 32) & 0xFFFFFFFF

        self.write_reg(low_val, lower)
        self.write_reg(up_val, upper)
