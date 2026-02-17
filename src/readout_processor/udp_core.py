import sys

from typing import Callable
from functools import partial
from ipaddress import ip_address

from RegisterAccessor.RegisterMap import Register, RegisterMap, RegisterMapDict

class UdpCore:

    def __init__(self, regMap: RegisterMap, core: int,
                 create_read_access: Callable[[Register], Callable[[], int]],
                 write_reg: Callable[[int | bytes, Register], None]):
        
        core_map: RegisterMapDict = regMap.map["udp_core_0_{}".format(core)]

        src_mac_upper: Register = next(regMap.getReg("udp_core_control_src_mac_addr_upper", core_map))
        src_mac_lower: Register = next(regMap.getReg("udp_core_control_src_mac_addr_lower", core_map))
        self.src_mac = (src_mac_lower, src_mac_upper)

        dst_mac_upper: Register = next(regMap.getReg("udp_core_control_dst_mac_addr_upper", core_map))
        dst_mac_lower: Register = next(regMap.getReg("udp_core_control_dst_mac_addr_lower", core_map))
        
        self.dst_mac = (dst_mac_lower, dst_mac_upper)

        self.src_ip: Register = next(regMap.getReg("udp_core_control_src_ip_addr", core_map))
        self.dst_ip: Register = next(regMap.getReg("udp_core_control_dst_ip_addr", core_map))

        self.tree = {
                "dest_ip": (partial(self.get_ip, create_read_access(self.dst_ip)),
                            partial(self.set_ip, self.dst_ip),
                            {"description": self.dst_ip.desc}),
                "src_ip":  (partial(self.get_ip, create_read_access(self.src_ip)),
                            partial(self.set_ip, self.src_ip),
                            {"description": self.src_ip.desc}),
                "src_mac": (partial(self.get_mac,
                                    create_read_access(self.src_mac[1]),
                                    create_read_access(self.src_mac[0])),
                            partial(self.set_mac, self.src_mac[1], self.src_mac[0]),
                            {"description": "Source MAC Address"}),
                "dest_mac": (partial(self.get_mac,
                                     create_read_access(self.dst_mac[1]),
                                     create_read_access(self.dst_mac[0])),
                             partial(self.set_mac, self.dst_mac[1], self.dst_mac[0]),
                             {"description": "Destination MAC Address"})
            }

        self.write_reg = write_reg

    
    def get_ip(self, read_accessor: Callable[[], int]) -> str:
        addr = ip_address(read_accessor())
        return addr.compressed
    
    def set_ip(self, reg: Register, val: str) -> None:
        addr = ip_address(val)
        val = addr.packed if sys.byteorder == "big" else addr.packed[::-1]
        self.write_reg(val, reg)

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

        self.write_reg(upper_val, upper_reg)
        self.write_reg(lower_val, lower_reg)