from pathlib import Path
import logging
import re


__version__ = "0.0.6"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


class InvalidIniFileEntryError(Exception): pass
class InvalidImgOffsetError(Exception): pass
class InvalidVirtualAddressError(Exception): pass


# Get non-overlapping intervals from interval by removing intervals_to_remove
# intervals_to_remove has to be sorted by left val
# return [[a,b], ...] or None
def remove_intervals_from_interval(interval:list, intervals_to_remove:list):
    interval = interval[:]
    result_intervals = []
    for interval_to_remove in intervals_to_remove:
        if interval_to_remove[2] < interval[1]: continue # end before
        if interval_to_remove[1] > interval[2]: break # begin after

        if interval_to_remove[1] <= interval[1]: # begin before
            if interval_to_remove[2] >= interval[2]: # total overlap
                return None
            interval[1] = interval_to_remove[2] # begin truncate
        elif interval_to_remove[2] >= interval[2]: # end truncate
            interval[2] = interval_to_remove[1]
            break
        else: # middle truncate
            result_intervals.append( ["empty", interval[1], interval_to_remove[1]] )
            interval[1] = interval_to_remove[2]

    return result_intervals + [interval]


# Parse an ini file and return a list of [ [virtual_address:int, value:bytes], ... ]
# All ARCodes present in the ini will be enabled without taking care of [ActionReplay_Enabled] section
# raise an Exception if lines are in invalid format:
# * empty lines are removed
# * lines beginning with $ are concidered as comments and are removed
# * lines beginning with [ are concidered as comments and are removed
# * others lines have to be in format: "0AXXXXXX XXXXXXXX" with A in [2,3,4,5] and X in [0-9a-fA-F]
def parse_action_replay_ini(path:Path):
    action_replay_lines = path.read_text().splitlines()

    # Address = (first 4 bytes & 0x01FFFFFF) | 0x80000000
    pattern = re.compile("^(0[2345][0-9a-zA-Z]{6}) ([0-9a-zA-Z]{8})$")
    result_list = []

    for action_replay_line in action_replay_lines:
        if len(action_replay_line) == 0:
            continue
        if action_replay_line[0] in ["$", "["]:
            continue
        res = pattern.fullmatch(action_replay_line)

        if res is None:
            raise InvalidIniFileEntryError(f"Error - Arcode has to be in format: '0AXXXXXX XXXXXXXX' with A in [2,3,4,5] and X in [0-9a-fA-F] line \"{action_replay_line}\".")

        virtual_address = (int(res[1], base=16) & 0x01FFFFFF) | 0x80000000
        opcode = int(res[1][:2], base=16) & 0xFE
        bytes_value = None
        if opcode == 0x04:
            bytes_value = int(res[2], 16).to_bytes(4, "big")
        elif opcode == 0x02:
            bytes_value = (int(res[2][:4], 16) + 1) * int(res[2][4:], 16).to_bytes(2, "big")
        else:
            raise InvalidIniFileEntryError("Error - Arcode has to be in format: '0AXXXXXX XXXXXXXX' with A in [2,3,4,5] and X in [0-9a-fA-F] line \"{action_replay_line}\".")
        result_list.append( (virtual_address, bytes_value) )
        """
        """
    return result_list


class Dol:
    HEADER_LEN = 0x100
    __path = None
    __header = None
    __data = None
    # List of 18 tuples [(offset, address, length, is_used), ] that describe all sections of the dol
    __sections_info = None
    # (address, length)
    __bss_info = None
    __entry_point = None
    def __init__(self, path:Path):
        self.__path = path
        data = path.read_bytes()
        self.__header = data[:Dol.HEADER_LEN]
        self.__data = data[Dol.HEADER_LEN:]

        self.__bss_info = ( int.from_bytes(data[0xd8:0xdc], "big"), int.from_bytes(data[0xdc:0xe0], "big") )
        self.__entry_point = int.from_bytes(data[0xe0:0xe4], "big")

        self.__sections_info = []
        for i in range(18):
            offset = int.from_bytes(data[i*4:i*4+4], "big")
            address = int.from_bytes(data[0x48+i*4:0x48+i*4+4], "big")
            length = int.from_bytes(data[0x90+i*4:0x90+i*4+4], "big")
            is_used = (offset != 0) and (address != 0) and (length != 0)
            self.__sections_info.append( (offset, address, length, is_used) )
    # print a table with each sections
    def __str__(self):
        res = f"Entry point: {self.__entry_point:08x}\n\n"
        res += "Section | Offset   | Address  | Length   | Used\n" + "-"*48 + "\n"
        i = 0
        for section in self.__sections_info:
            res+= "text"+str(i) if i < 7 else "data"+str(i)
            if i < 10: res += " "
            res += f"  | {section[0]:08x} | {section[1]:08x} | {section[2]:08x} | {str(section[3])}\n"
            i += 1
        res += f"\nbss: address:{self.__bss_info[0]:08x} length:{self.__bss_info[1]:08x}"
        return res
    """
    # search_raw: bytecode
    # we could also identify text segments to improve search
    def search_raw(self, bytecode:bytes):
        if len(bytecode) == 0:
            raise Exception("Error - No bytecode.")
        offsets = []
        for i in range(len(self.__data) - len(bytecode) + 1):
            if self.__data[i:i+len(bytecode)] == bytecode:
                offsets.append(self.resolve_img2virtual(i + Dol.HEADER_LEN))
        return offsets if len(offsets) > 0 else None
    """
    # Resolve a dol absolute offset to a virtual memory address
    def resolve_img2virtual(self, offset:int):
        memory_address = None
        for section_info in self.__sections_info:
            if not section_info[3]: continue
            if offset >= section_info[0] and offset < section_info[0] + section_info[2]:
                return section_info[1] + offset - section_info[0]
        raise InvalidImgOffsetError(f"Not found: {offset:08x}")
    # Resolve a virtual memory address to a dol absolute offset
    def resolve_virtual2img(self, address:int):
        for section_info in self.__sections_info:
            if not section_info[3]: continue
            if address >= section_info[1] and address < section_info[1] + section_info[2]:
                return section_info[0] + address - section_info[1]
        raise InvalidVirtualAddressError(f"Not found in dol initial segments: {address:08x}")
    def stats(self):
        print(self)

        # https://www.gc-forever.com/yagcd/chap4.html#sec4
        # system:      0x80000000 -> 0x80003100
        # available:   0x80003100 -> 0x81200000
        # apploader:   0x81200000 -> 0x81300000
        # Bootrom/IPL: 0x81300000 -> 0x81800000

        # Now we have to generate a memory map with splited bss and empty spaces
        # [ [section_name, beg_addr, end_addr, length], ... ]
        result_intervals = [
            ["system", 0x80000000, 0x80003100, 0x3100],
            ["apploader", 0x81200000, 0x81300000, 0x100000],
            ["Bootrom/IPL", 0x81300000, 0x81800000, 0x500000]]

        i = 0
        for section in self.__sections_info[:7]:
            if section[3]:
                result_intervals.append( [f".text{i}", section[1], section[1] + section[2], section[2]] )
                i += 1

        i = 0
        for section in self.__sections_info[7:18]:
            if section[3]:
                result_intervals.append( [f".data{i}", section[1], section[1] + section[2], section[2]] )
                i += 1

        result_intervals.sort(key=lambda x: x[1])
        i = 0
        for bss_interval in remove_intervals_from_interval([None, self.__bss_info[0], self.__bss_info[0] + self.__bss_info[1]], result_intervals):
            result_intervals.append( [f".bss{i}", bss_interval[1], bss_interval[2], bss_interval[2] - bss_interval[1]] )
            i += 1

        # We search now available program space
        result_intervals.sort(key=lambda x: x[1])
        empty_intervals = remove_intervals_from_interval(["empty", 0x80003100, 0x81200000], result_intervals)
        for empty_interval in empty_intervals:
            result_intervals += [[empty_interval[0], empty_interval[1], empty_interval[2], empty_interval[2] - empty_interval[1]]]

        result_intervals.sort(key=lambda x: x[1])
        str_buffer = "\nSection      | beg_addr | end_addr | length   |\n" + "-"*48 + "\n"
        for interval in result_intervals:
            str_buffer += f"{interval[0].ljust(12)} | {interval[1]:08x} | {interval[2]:08x} | {interval[3]:08x} | \n"

        print(str_buffer)
    def extract(self, filename:str, section_index:int):
        if section_index > 17:
            raise Exception("Error - Section index has to be in 0 - 17")

        begin_offset = self.__sections_info[section_index][0] - self.HEADER_LEN
        end_offset = begin_offset + self.__sections_info[section_index][2]

        section_type = "text" if section_index < 7 else "data"
        Path(f"{filename}_{section_type}{section_index}").write_bytes(self.__data[begin_offset:end_offset])
    # [ [virtual_address:int, value:bytes], ... ]
    def patch_action_replay(self, virtualaddress_bytes_list:list):
        self.__data = bytearray(self.__data)
        for virtualaddress_bytes in virtualaddress_bytes_list:
            offset = self.resolve_virtual2img(virtualaddress_bytes[0])
            print(f"Patching {virtualaddress_bytes[0]:08x} at dol offset {offset:08x} with value {virtualaddress_bytes[1].hex()}")
            self.__data[offset: offset + len(virtualaddress_bytes[1])] = virtualaddress_bytes[1]


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='dol file format utilities - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('arg2', metavar='arg2', help='', nargs='?', default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-v2i', '--virtual2image', action='store_true', help="-v2i source.dol virtual_address: Translate a virtual address into a dol offset if this was originaly mapped from data or text. virtual_address has to be in hexadecimal: 80003100.")
    group.add_argument('-i2v', '--image2virtual', action='store_true', help="-i2b source.dol dol_offset: Translate a dol offset to a virtual address mapped from data or text. dol_offset has to be in hexadecimal: 2000.")
    group.add_argument('-s', '--stats', action='store_true', help="-s source.dol: Get stats about entry point, sections, bss and unused virtual address space.")
    group.add_argument('-e', '--extract', action='store_true', help="-e source.dol section_index: Extract a section. index must be between 0 and 17")
    group.add_argument('-par', '--patch-action-replay', action='store_true', help="-p source.dol action_replay.ini: Patch initialised data inside the dol with an ini file containing a list of [write] directives. Handle only ARCodes beginning with 04.")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not p_input.is_file():
        raise Exception("Error - Invalid dol file path.")

    dol = Dol(p_input)

    if args.virtual2image:
        if args.arg2 is None:
            raise Exception("Error - Virtual address has to be specified in hexadecimal: 80003000.")
        virtual_address = int(args.arg2, 16)
        try:
            offset = dol.resolve_virtual2img(virtual_address)
            print(f"Virtual address {virtual_address:08x} is at dol offset {offset:08x}")
        except InvalidVirtualAddressError:
            print("This virtual address is not in the dol.")
    elif args.image2virtual:
        if args.arg2 is None:
            raise Exception("Error - dol offset has to be specified in hexadecimal: 1234.")
        offset = int(args.arg2, 16)
        try:
            virtual_address = dol.resolve_img2virtual(offset)
            print(f"Dol offset {offset:08x} is at virtual address {virtual_address:08x}")
        except InvalidImgOffsetError:
            print("This dol offset is invalid.")
    elif args.stats:
        dol.stats()
    elif args.extract:
        logging.info("### Extract section")
        if args.arg2 is None:
            raise Exception("Error - Section index has to be specified.")
        index = int(args.arg2)

        section_type = "text" if index < 7 else "data"
        logging.info(f"Extracting section {index} in file {p_input.name}_{section_type}{index}...")
        dol.extract(p_input.name, index)
    elif args.patch_action_replay:
        logging.info("### Patch dol using Action Replay ini file")
        if args.arg2 is None:
            raise Exception("Error - Action Replay ini file has to be specified.")
        action_replay_ini_path = Path(args.arg2)
        if not action_replay_ini_path.is_file():
            raise Exception("Error - Invalid action replay ini file path.")

        logging.info(f"Patching dol {p_input} using .ini file {action_replay_ini_path}...")
        dol.patch_action_replay(parse_action_replay_ini(action_replay_ini_path))
