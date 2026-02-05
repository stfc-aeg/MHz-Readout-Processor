import logging
from odin.adapters.parameter_tree import ParameterTree, ParameterTreeError
from RegisterAccessor.controller import RegisterAccessorController, ControllerError
from RegisterAccessor.RegisterMap import Register
from .udp_core import UdpCore
from ipaddress import ip_address

from typing import Callable
from functools import partial

class ReadoutProcessorError(ControllerError):
    """Simple exception class to wrap lower-level exceptions."""


class ReadoutProcessorController(RegisterAccessorController):
    """Controller class for READOUTPROCESSOR."""

    def __init__(self, options):
        super().__init__(options)

        # overriding RegisterAccessor Param Tree creation
        tree = {}
        tree["control"] = {
            "open": (None, lambda _: self.open_device(), {"description": "Open connetion to the device"}),
            "close": (None, lambda _: self.accessor.close(), {"description": "Close connetion to the device"}),
            "connected": (lambda: self.accessor.isConnected, None)
        }

        udp_0 = UdpCore(self.register_map, 0)
        udp_1 = UdpCore(self.register_map, 1)


        tree["udp"] = {
            "core_0": {
                "dest_ip": (partial(self.get_ip, self.create_read_access_param(udp_0.dst_ip)),
                            partial(self.set_ip, udp_0.dst_ip),
                            {"description": udp_0.dst_ip.desc}),
                "src_ip":  (partial(self.get_ip, self.create_read_access_param(udp_0.src_ip)),
                            partial(self.set_ip, udp_0.src_ip),
                            {"description": udp_0.src_ip.desc}),
                "src_mac": (partial(self.get_mac,
                                    self.create_read_access_param(udp_0.src_mac[1]),
                                    self.create_read_access_param(udp_0.src_mac[0])),
                            partial(self.set_mac, udp_0.src_mac[1], udp_0.src_mac[0]),
                            {"description": "Source MAC Address"}),
                "dest_mac": (partial(self.get_mac,
                                    self.create_read_access_param(udp_0.dst_mac[1]),
                                    self.create_read_access_param(udp_0.dst_mac[0])),
                            partial(self.set_mac, udp_0.dst_mac[1], udp_0.dst_mac[0]),
                            {"description": "Destination MAC Address"})
            },
            "core_1": {
                "dest_ip": (partial(self.get_ip, self.create_read_access_param(udp_1.dst_ip)),
                            partial(self.set_ip, udp_1.dst_ip),
                            {"description": udp_1.dst_ip.desc}),
                "src_ip":  (partial(self.get_ip, self.create_read_access_param(udp_1.src_ip)),
                            partial(self.set_ip, udp_1.src_ip),
                            {"description": udp_1.src_ip.desc}),
                "src_mac": (partial(self.get_mac,
                                    self.create_read_access_param(udp_1.src_mac[1]),
                                    self.create_read_access_param(udp_1.src_mac[0])),
                            partial(self.set_mac, udp_1.src_mac[1], udp_1.src_mac[0]),
                            {"description": "Source MAC Address"}),
                "dest_mac": (partial(self.get_mac,
                                    self.create_read_access_param(udp_1.dst_mac[1]),
                                    self.create_read_access_param(udp_1.dst_mac[0])),
                            partial(self.set_mac, udp_1.dst_mac[1], udp_1.dst_mac[0]),
                            {"description": "Destination MAC Address"})
            }
        }
        aurora_lane: Register = next(self.register_map.getReg("aurora_lane_up"))
        aurora_channel: Register = next(self.register_map.getReg("aurora_chan_up"))
        control_reg: Register = next(self.register_map.getReg("hexitec_mhz_front_end_hexitec_hist_frame_generator_acq_ctrl"))
        clock_resets: Register = next(self.register_map.getReg("domain_resets"))
        frameNum_upper: Register = next(self.register_map.getReg("hexitec_mhz_front_end_hexitec_hist_frame_generator_frame_number_upper"))
        frameNum_lower: Register = next(self.register_map.getReg("hexitec_mhz_front_end_hexitec_hist_frame_generator_frame_number_lower"))

        clock_resets_tree = self.create_reg_paramTree(clock_resets)['fields']
        selected_resets = {k: clock_resets_tree[k] for k in 
                           ("cmac_0_reset", "cmac_1_reset", "cmac_2_reset", "aurora_reset", "data_path_reset")}
        control_tree = self.create_reg_paramTree(control_reg)['fields']
        tree["status"] = {
            "aurora_lane": (partial(self.get_bool, self.create_read_access_param(aurora_lane)),
                               None, {"description": aurora_lane.desc}),
            "aurora_channel": (partial(self.get_bool, self.create_read_access_param(aurora_channel)),
                               None, {"description": aurora_channel.desc}),
            "frame_number": (partial(self.get_frameNum,
                                     self.create_read_access_param(frameNum_upper),
                                     self.create_read_access_param(frameNum_lower)),
                             None, {"description": "Current Frame number, 48 bit value"}),
            "clock_resets": selected_resets,
            "acq_control": control_tree
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
        
    def get_ip(self, read_accessor: Callable[[], int]) -> str:
        addr = ip_address(read_accessor())
        return addr.compressed

    def set_ip(self, reg: Register, val: str) -> None:
        addr = ip_address(val)
        self.write_register(addr.packed[::-1], reg)

    def get_mac(self, read_access_upper: Callable[[], int], read_access_lower: Callable[[], int]) -> str:
        upper_val = read_access_upper()
        lower_val = read_access_lower()

        full_val = lower_val | (upper_val << 32)
        parts = [
            (full_val >> 40) & 0xFF,
            (full_val >> 32) & 0xFF,
            (full_val >> 24) & 0xFF,
            (full_val >> 16) & 0xFF,
            (full_val >> 8)  & 0xFF,
            (full_val) & 0xFF
        ]
        return ":".join(f"{val:02X}" for val in parts)
    
    def set_mac(self, upper_reg: Register, lower_reg: Register, val: str) -> None:

        parts = [int(x, 16) for x in val.split(":")]

        upper_val = (parts[0] << 8) | parts[1]
        lower_val = (parts[2] << 24) | (parts[3] << 16) | (parts[4] << 8) | parts[5]

        self.write_register(upper_val, upper_reg)
        self.write_register(lower_val, lower_reg)

    def get_bool(self, read_accessor: Callable[[], int]):
        return bool(read_accessor())
    
    def get_frameNum(self, read_access_upper: Callable[[], int], read_access_lower: Callable[[], int]) -> str:
        upper = read_access_upper()
        lower = read_access_lower()

        return lower | (upper << 32)

