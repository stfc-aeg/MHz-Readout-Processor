
import logging
from dataclasses import dataclass
from enum import IntFlag, auto
from functools import partial
from typing import Callable

from odin.adapters.parameter_tree import ParameterTree, ParameterTreeError
from RegisterAccessor.controller import RegisterAccessorController, ControllerError
from RegisterAccessor.RegisterMap import Register

from .udp_core import UdpCore


class ReadoutProcessorError(ControllerError):
    """Simple exception class to wrap lower-level exceptions."""


@dataclass
class ReadoutRegisters:
    """Container for the registers required to montior and reset the Data Readout"""
    aurora_lane: Register = None
    aurora_channel: Register = None
    acq_control: Register = None
    clock_resets: Register = None
    frame_num_upper: Register = None
    frame_num_lower: Register = None
    cmac_status: Register = None


class ConnectionStatus(IntFlag):
    LANE = auto()
    CHAN = auto()
    CMAC_0 = auto()
    CMAC_1 = auto()


class ReadoutProcessorController(RegisterAccessorController):
    """Controller class for READOUTPROCESSOR."""

    SELECT_REGS = {"aurora_lane": "aurora_lane_up",
                   "aurora_channel": "aurora_chan_up",
                   "acq_control": "hexitec_mhz_front_end_hexitec_hist_frame_generator_acq_ctrl",
                   "clock_resets": "domain_resets",
                   "frame_num_upper": "hexitec_mhz_front_end_hexitec_hist_frame_generator"
                                      "_frame_number_upper",
                   "frame_num_lower": "hexitec_mhz_front_end_hexitec_hist_frame_generator"
                                      "_frame_number_lower",
                   "cmac_status": "cmac_status"}
    """Dict of specific registers to get from the full register map"""

    def __init__(self, options):
        super().__init__(options)

        # overriding RegisterAccessor Param Tree creation
        tree = {}
        tree["control"] = {
            "open": (None, lambda _: self.open_device(),
                     {"description": "Open connection to the device"}),
            "close": (None, lambda _: self.accessor.close(),
                      {"description": "Close connection to the device"}),
            "connected": (lambda: self.accessor.isConnected, None)
        }

        # setup UDP trees
        udp_0 = UdpCore(self.register_map, 0,
                        self.create_read_access_param, self.write_register)
        udp_1 = UdpCore(self.register_map, 1,
                        self.create_read_access_param, self.write_register)

        tree["udp"] = {
            "core_0": udp_0.tree,
            "core_1": udp_1.tree
        }
        # get the specific registers needed to monitor/reset the readout device
        try:
            self.registers: ReadoutRegisters = ReadoutRegisters()
            for key, val in self.SELECT_REGS.items():
                regs = self.register_map.getReg(val)
                setattr(self.registers, key, next(regs))
        except StopIteration:
            logging.error("One of the required Registers could not be found in the Register Map.")

        clock_resets_tree = self.create_reg_paramTree(self.registers.clock_resets)['fields']
        selected_resets = {k: clock_resets_tree[k] for k in
                           ("cmac_0_reset", "cmac_1_reset", "cmac_2_reset",
                            "aurora_reset", "data_path_reset")}

        control_tree = self.create_reg_paramTree(self.registers.acq_control)['fields']

        cmac_tree = self.create_reg_paramTree(self.registers.cmac_status)['fields']
        selected_cmac = {k: cmac_tree[k] for k in ("cmac_0_lane_up", "cmac_1_lane_up")}

        aurora_lane_read = self.create_read_access_param(self.registers.aurora_lane)
        aurora_chan_read = self.create_read_access_param(self.registers.aurora_channel)

        frame_num_upper_read = self.create_read_access_param(self.registers.frame_num_upper)
        frame_num_lower_read = self.create_read_access_param(self.registers.frame_num_lower)

        # value for an active aurora lane/channel.
        # Any other value means something is wrong
        self.aurora_good_val = 0xFFFFF

        tree["status"] = {
            "is_running": (self.get_connection_status, None,
                           {"description": "Represents if the readout device is correctly running"
                            ". If false, check aurora and cmac values"}),
            "reset": (None, lambda _: self.reset(),
                      {"description": "Reset the readout device, if something is wrong."}),
            "reactivate": (None, lambda _: self.setup_after_reset(),
                           {"description": "Reactivate readout after a reset process"}),
            "aurora": {
                "lane": (lambda: aurora_lane_read() == self.aurora_good_val, None,
                         {"description": "Aurora Lane Status"}),
                "channel": (lambda: aurora_chan_read() == self.aurora_good_val, None,
                            {"description": "Aurora Channel Status"})
            },
            "frame_number": (partial(self.get_frame_num,
                                     frame_num_upper_read, frame_num_lower_read),
                             None, {"description": "Current Frame number, 48 bit value"}),
            "clock_resets": selected_resets,
            "acq_control": control_tree,
            "cmac": selected_cmac
        }

        self.param_tree = ParameterTree(tree)

    def initialize(self, adapters):
        self.adapters = adapters
        logging.debug(f"Adapters initialized: {list(adapters.keys())}")

    def cleanup(self):
        logging.info("Cleaning up ReadoutProcessorController")

    def get(self, path, with_metadata=False):
        try:
            return self.param_tree.get(path, with_metadata)
        except (ParameterTreeError, ControllerError) as error:
            logging.error(error)
            raise ReadoutProcessorError(error)

    def set(self, path, data):
        try:
            self.param_tree.set(path, data)
        except (ParameterTreeError, ControllerError) as error:
            logging.error(error)
            raise ReadoutProcessorError(error)

    def get_frame_num(self, read_access_upper: Callable[[], int],
                      read_access_lower: Callable[[], int]) -> str:
        upper = read_access_upper()
        lower = read_access_lower()

        return lower | (upper << 32)

    def get_connection_status(self) -> bool:
        status = True

        chan = self.registers.aurora_channel
        lane = self.registers.aurora_lane
        cmac = self.registers.cmac_status

        # using "next" to get the first bit in the bitfield that matches
        # the name. Should only be one, but is tidier than getting it
        # using an index
        cmac_0 = next(bit for bit in cmac.bitFields
                      if bit.name == "cmac_0_lane_up")
        cmac_1 = next(bit for bit in cmac.bitFields
                      if bit.name == "cmac_1_lane_up")

        # this value means the aurora chan/lane values are valid.
        aurora_good_val = 0xFFFFF

        if self.read_register(chan) != aurora_good_val:
            status = False
        if self.read_register(lane) != aurora_good_val:
            status = False
        if not self.read_field(cmac, cmac_0):
            status = False
        if not self.read_field(cmac, cmac_1):
            status = False
        return status

    def reset(self):
        """Trigger a reset of the Readout device. Based on state machine in
        Mhz Detector, turns off bits in control reg and toggles reset bits
        HIGH then LOW to trigger reset"""

        logging.debug("Readout Manual trigger and acquire OFF")
        control = self.registers.acq_control
        resets = self.registers.clock_resets

        control_fields = [bit for bit in control.bitFields
                          if bit.name in ("acquire", "manual_trig")]
        reset_fields = [bit for bit in resets.bitFields
                        if bit.name in ("data_path_reset", "aurora_reset",
                                        "cmac_0_reset", "cmac_1_reset", "cmac_2_reset")]
        try:
            # disable acquire and manual trigger bits
            for bit in control_fields:
                self.write_field(0, control, bit)

            # toggle reset bits high then low
            for bit in reset_fields:
                self.write_field(1, resets, bit)
                self.write_field(0, resets, bit)

        except (ReadoutProcessorError, ControllerError) as err:
            logging.error("RESET FAILED: %s", err)

    def setup_after_reset(self):
        """Turn Manual trigger and acquire back on after a successful reset"""

        logging.debug("Manual trigger and acquire ON")
        control = self.registers.acq_control

        control_fields = [bit for bit in control.bitFields
                          if bit.name in ("acquire", "manual_trig")]

        try:
            for bit in control_fields:
                self.write_field(1, control, bit)
        except (ReadoutProcessorError, ControllerError) as err:
            logging.error("SETUP AFTER RESET FAILED: %s", err)
