from RegisterAccessor.RegisterMap import Register, RegisterMap, RegisterMapDict

class UdpCore:

    def __init__(self, regMap: RegisterMap, core: int):
        
        core_map: RegisterMapDict = regMap.map["udp_core_0_{}".format(core)]

        src_mac_upper: Register = next(regMap.getReg("udp_core_control_src_mac_addr_upper", core_map))
        src_mac_lower: Register = next(regMap.getReg("udp_core_control_src_mac_addr_lower", core_map))
        self.src_mac = (src_mac_lower, src_mac_upper)

        dst_mac_upper: Register = next(regMap.getReg("udp_core_control_dst_mac_addr_upper", core_map))
        dst_mac_lower: Register = next(regMap.getReg("udp_core_control_dst_mac_addr_lower", core_map))
        
        self.dst_mac = (dst_mac_lower, dst_mac_upper)

        self.src_ip: Register = next(regMap.getReg("udp_core_control_src_ip_addr", core_map))
        self.dst_ip: Register = next(regMap.getReg("udp_core_control_dst_ip_addr", core_map))
