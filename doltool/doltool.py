import copy
import enum
import logging
from pathlib import Path
import re


__version__ = "0.0.9"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


# raised when the action replay ini file contains a bad formated entry
class InvalidIniFileEntryError(Exception): pass
# raised when trying to resolve an invalid dol file offset
class InvalidImgOffsetError(Exception): pass
# raised when trying to resolve an out of section Virtual address
class InvalidVirtualAddressError(Exception): pass
# raised when Virtual address + length Overflow out of sections
class SectionsOverflowError(Exception): pass
# raised when Virtual address + length is out of main program space memory
class OutOfMemoryError(Exception): pass
# raised when Virtual address of used section is unaligned to 32 bytes
class InvalidSectionAlignError(Exception): pass
# raised when Section offset does not match current file datas
class InvalidSectionOffsetError(Exception): pass


def align_bottom(address:int, align:int):
    if address % align == 0: return address
    return address - address % align


def align_top(address:int, align:int):
    if address % align == 0: return address
    return address + align - (address % align)


class SectionType(enum.IntFlag):
    DATA = 0
    TEXT = 1
    BSS = 2
    SYS = 3
    UNMAPPED = 4


class IntervalDiv(enum.IntFlag):
    LEFT = 0
    IN = 1
    RIGHT = 2


class MemoryObject:
    __locked_address_space = None
    __type = None
    __name = None
    __address = None
    __end_address = None
    __length = None
    __datas = None
    def __init__(self, address:int, section_type:SectionType = SectionType.UNMAPPED, name:str = None, length:int = None, end_address:int = None, locked_address_space:bool = True):
        if length is None:
            if end_address is None:
                raise Exception("Error - length or end_address has to be specified.")
            self.__end_address = end_address
            self.__length = end_address - address
        else:
            self.__length = length
            self.__end_address = address + length

        if section_type == section_type.SYS or not locked_address_space:
            self.__locked_address_space = False
        else:
            self.__locked_address_space = True
            if not 0x80003100 <= address < 0x81200000 or not 0x80003100 < self.__end_address <= 0x81200000:
                raise OutOfMemoryError(f"Error - Out of memory address: {address:08x}:{self.__end_address:08x}: should be in 0x80003100:0x81200000.")

        self.__type = section_type
        self.__name = name
        self.__address = address
    def __str__(self):
        return f"| {str(self.name()).ljust(11)} | {self.address():08x} | {self.end_address():08x} | {self.length():08x} |"
    def __sub__(interval:'MemoryObject', intervals_to_remove:list):
        """
        Get non-overlapping intervals from interval by removing intervals_to_remove
        input: interval = MemoryObject
        input: intervals_to_remove = [ MemoryObject, ... ]
        return [MemoryObject, ...] or None
        * sorted by address
        """
        interval = copy.deepcopy(interval)
        intervals_to_remove.sort(key=lambda x: x.address())
        result_memory_objects = []
        for interval_to_remove in intervals_to_remove:
            if interval_to_remove < interval:  continue # end before
            if interval_to_remove > interval:  break # begin after
            if interval in interval_to_remove: return result_memory_objects if result_memory_objects != [] else None # total overlap

            # begin truncate
            if interval_to_remove.address() <= interval.address():
                interval.set_address(interval_to_remove.end_address())
                continue
            result_memory_objects.append(MemoryObject(interval.address(), interval.type(), interval.name(), end_address=interval_to_remove.address()))
            
            # end truncate
            if interval_to_remove.end_address() >= interval.end_address():
                return result_memory_objects
            # interval.address() < interval_to_remove < interval.end_address()
            interval.set_address( interval_to_remove.end_address() )
            continue
        if interval.length() > 0:
            result_memory_objects.append(interval)
        return result_memory_objects if result_memory_objects != [] else None
    def __lt__(a, b):       return a.end_address() <= b.address()
    def __le__(a, b):       return b.address() < a.end_address() <= b.end_address() and a.address() < b.address()
    def __ge__(a, b):       return b.address() <= a.address() < b.end_address() and a.end_address() > b.end_address()
    def __gt__(a, b):       return a.address() >= b.end_address()
    def __contains__(a, b): return b.address() >= a.address() and b.end_address() <= a.end_address()
    def __and__(a, b):      return a.address() < b.end_address() and a.end_address() > b.address() # Intersect
    def __truediv__(a, b):
        """
        Description: Split a using b by creating before_b, in_b, after_b intervals
        input: a = MemoryObject or inherited class
        input: b = MemoryObject or inherited class
        return: {IntervalDiv: splited_copy, ... } or None
        """
        if not a & b: return None
        result = {}

        if a.address() < b.address():
            new_left = copy.deepcopy(a)
            
            new_left.set_end_address(b.address())
            new_left.set_datas( new_left.datas()[:new_left.length()] )

            a.set_address(b.address())
            a.set_datas( a.datas()[-a.length():] )

            result[IntervalDiv.LEFT] = new_left

        if a.end_address() > b.end_address():
            new_right = copy.deepcopy(a)
            new_right.set_address(b.end_address())
            new_right.set_datas( new_right.datas()[-new_right.length():] )
                        
            a.set_end_address(b.end_address())
            a.set_datas( a.datas()[:a.length()] )

            result[IntervalDiv.RIGHT] = new_right

        result[IntervalDiv.IN] = a
        return result if len(result) > 0 else None
    #__eq__(a, b)
    def type(self):         return self.__type
    def name(self):         return self.__name
    def address(self):      return self.__address
    def end_address(self):  return self.__end_address
    def length(self):       return self.__length
    def datas(self):        return self.__datas
    def set_name(self, name:str):     self.__name = name
    def set_address(self, address:int):
        if self.__locked_address_space and not 0x80003100 <= address < 0x81200000:
            raise OutOfMemoryError(f"Error - Out of memory address: {address:08x} should be 0x80003100 <= address < 0x81200000.")
        self.__address = address
        self.__length = self.__end_address - address
    def set_end_address(self, address:int):
        if self.__locked_address_space and not 0x80003100 < address <= 0x81200000:
            raise OutOfMemoryError(f"Error - Out of memory end_address: {address:08x} should be 0x80003100 < end_address <= 0x81200000.")
        self.__end_address = address
        self.__length = address - self.__address
    def set_datas(self, datas:bytes):
        self.__datas = datas
    def set_type(self, section_type:SectionType):
        self.__type = section_type
    def update_datas(self, memory_object:'MemoryObject'):
        if not memory_object in self:
            raise Exception("Error - Invalid update adresses.")
        if len(memory_object.datas()) != memory_object.length():
            raise Exception("Error - length does not match the datas length.")
        self.__datas = bytearray(self.__datas)
        offset = memory_object.address() - self.address()
        self.__datas[offset: offset + memory_object.length()] = memory_object.datas()
    def to_memory_object(self): return MemoryObject(self.address(), self.type(), self.name(), length=self.length())
    def align(self):
        self.set_address( align_bottom(self.address(), 32) )
        self.set_end_address( align_top(self.end_address(), 32) )


class Section(MemoryObject):
    __index = None
    __offset = None
    __is_used = None
    def __init__(self, index:int, offset:int, address:int, length:int, section_type:SectionType = None):
        if section_type is None:
            section_type = SectionType.TEXT if index < 7 else SectionType.DATA
        super().__init__(address, section_type, length=length, locked_address_space=False)
        self.__index = index
        self.__offset = offset
        if self.is_used():
            # Section virtual address has to be aligned to 32 bytes.
            if self.address() % 32 != 0:
                raise InvalidSectionAlignError(f"Error - Section {index} is not aligned to 32 bytes.")
    def index(self):       return self.__index
    def offset(self):      return self.__offset
    def set_index(self, index:int):   self.__index = index
    def set_offset(self, offset:int): self.__offset = offset
    def is_used(self):
        return (self.__offset != 0) and (self.address() != 0) and (self.length() != 0)
    def format_raw(self):
        section_raw_name = f"text{self.index()}".ljust(7) if self.type() == SectionType.TEXT else f"data{self.index()}".ljust(7)
        return f"| {section_raw_name} | {self.offset():08x} | {self.address():08x} | {self.length():08x} | {str(self.is_used()).ljust(5)} |\n"
    def resolve_img2virtual(self, offset:int):
        if offset >= self.offset() and offset < self.offset() + self.length():
            return self.address() + offset - self.offset()
        return None
    def resolve_virtual2img(self, address:int):
        if address >= self.address() and address < self.end_address():
            return self.offset() + address - self.address()
        return None


class Bss(MemoryObject):
    # list of memory objects out of sections
    __splited = None
    def __init__(self, address:int, length:int):
        super().__init__(address, SectionType.BSS, "bss", length=length)
    def format(self):
        return f"bss: address:{self.address():08x} length:{self.length():08x}"
    def split(self, memory_objects:list):
        self.__splited = self - memory_objects
        if self.__splited is not None: # If .bss is mapped
            for i, splited in enumerate(self.__splited):
                splited.set_name(f".bss{i}")
        return self.__splited
    def splited(self): return self.__splited


def get_unmapped_intervals(merged_intervals:list, memory_objects:list):
    """
    Description: This function is usefull to find new sections to create for an .ini file processing
    input: merged_intervals = [MemoryObject, ...]
    * non overlapping, with length > 0 (There is always sections in dols)
    input: memory_objects = [ActionReplayCode, ...]
    * could overlap
    return [MemoryObject, ...] else None
    * unmapped sections intervals where we found ARCodes sorted by address
    * it means that this intervals are used but are not in already existing intervals (merged_intervals)
    """
    memory_objects.sort(key=lambda x:x.address())
    unoverlapped_list = []
    for memory_object in memory_objects:
        unoverlapped = memory_object - merged_intervals
        if unoverlapped is not None:
            unoverlapped_list += unoverlapped

    if len(unoverlapped_list) == 0:
        return None

    merged_intervals = copy.deepcopy(merged_intervals)
    unoverlapped_list.sort(key=lambda x:x.address())
    def _get_unmapped_intervals(merged_intervals:list, unoverlapped_list:list):
        """
        input: merged_intervals: [MemoryObject, ...]
        * contains intervals separated by empty interval
        input: unoverlapped_list: [MemoryObject, ...]
        * contains intervals < merged_intervals or intervals > merged_intervals
        return [MemoryObject, ...]
        * each of the returned memory objects describe an unmapped interval used by unoverlapped_list
        """
        if len(merged_intervals) == 0:
            return [MemoryObject(unoverlapped_list[0].address(), end_address=unoverlapped_list[-1].end_address())]
        merged_interval = merged_intervals.pop(0)
        new_unmapped = []
        for i, memory_object in enumerate(unoverlapped_list):
            if memory_object < merged_interval:
                if new_unmapped == []:
                    new_unmapped = [memory_object]
                    continue
                else:
                    new_unmapped[0].set_end_address(memory_object.end_address())
                    continue
            else:
                if len(unoverlapped_list[i:]) == 0: return new_unmapped
                return new_unmapped + _get_unmapped_intervals(merged_intervals, unoverlapped_list[i:])
        return new_unmapped
    return _get_unmapped_intervals(merged_intervals, unoverlapped_list)


def get_overlapping_arcodes(action_replay_list:list):
    """
    input: action_replay_list = [ActionReplayCode, ...]
    return [(ActionReplayCode, ActionReplayCode), ...] else None
    Get overlapping action replay code in memory. Return couples of arcodes that patch sames memory addresses.
    """
    if len(action_replay_list) < 2: return None
    action_replay_list.sort(key=lambda x:x.address())

    # Find overlaps between ARCodes
    overlaps_list = []
    last_arcode = action_replay_list[0]
    for action_replay_code in action_replay_list[1:]:
        # Intersect
        if last_arcode & action_replay_code:
            overlaps_list.append( (last_arcode, action_replay_code) )
        last_arcode = action_replay_code
    return overlaps_list if overlaps_list != [] else None


def parse_action_replay_ini(path:Path):
    """
    input: path of ini
    return [ActionReplayCode, ...]
    Parse an ini file. All ARCodes present in the ini will be enabled without taking care of [ActionReplay_Enabled] section.
    * empty lines are removed
    * lines beginning with $ are concidered as comments and are removed
    * lines beginning with [ are concidered as comments and are removed
    * others lines have to be in format: "0AXXXXXX XXXXXXXX" with A in [0,1,2,3,4,5] and X in [0-9a-fA-F]
    """
    return [ActionReplayCode(action_replay_line, i + 1) for i, action_replay_line in enumerate(path.read_text().splitlines()) if len(action_replay_line) != 0 and action_replay_line[0] not in ["$", "["]]


class ActionReplayCode(MemoryObject):
    __PATTERN = re.compile("^(0[012345][0-9a-zA-Z]{6}) ([0-9a-zA-Z]{8})$") # class variable give better perfs for regex processing
    __line_number = None
    __opcode = None
    def __init__(self, action_replay_code:str, line_number:int):
        self.__line_number = line_number
        res = ActionReplayCode.__PATTERN.fullmatch(action_replay_code)

        if res is None:
            raise InvalidIniFileEntryError(f"Error - Arcode has to be in format: '0AXXXXXX XXXXXXXX' with A in [0,1,2,3,4,5] and X in [0-9a-fA-F] line {line_number} \"{action_replay_code}\".")

        # address = (first 4 bytes & 0x01FFFFFF) | 0x80000000
        address = (int(res[1], base=16) & 0x01FFFFFF) | 0x80000000

        # opcode = first byte & 0xFE
        self.__opcode = int(res[1][:2], base=16) & 0xFE
        if self.__opcode not in [0, 2, 4]:
            raise InvalidIniFileEntryError(f"Error - ARCode has to be in format: '0AXXXXXX XXXXXXXX' with A in [0,1,2,3,4,5] and X in [0-9a-fA-F] line {line_number} \"{action_replay_code}\".")

        if self.__opcode == 0x04:
            datas = int(res[2], 16).to_bytes(4, "big")
        elif self.__opcode == 0x02:
            datas = (int(res[2][:4], 16) + 1) * int(res[2][4:], 16).to_bytes(2, "big")
        elif self.__opcode == 0x00:
            datas = (int(res[2][:6], 16) + 1) * int(res[2][6:], 16).to_bytes(1, "big")

        length = len(datas)

        try:
            super().__init__(address, SectionType.UNMAPPED, action_replay_code, length=length)
        except OutOfMemoryError:
            raise OutOfMemoryError(f"Error - Out of memory address line {line_number}: {address:08x}:{address + length} should be in 0x80003100:0x81200000.")
        self.set_datas(datas)
    def __str__(self):
        return f"| {str(self.__line_number).rjust(8)} | {self.name()} | {self.address():08x} | {self.end_address():08x} | {self.length():08x} |"
    def __eq__(a, b): return a.name() == b.name() and a.address() == b.address() and a.end_address() == b.end_address() and a.__line_number == b.__line_number and a.__opcode == b.__opcode and a.datas() == b.datas()
    def __ne__(a, b): return a.name() != b.name() or a.address() != b.address() or a.end_address() != b.end_address() or a.__line_number != b.__line_number or a.__opcode != b.__opcode or a.datas() != b.datas()
    def line_number(self): return self.__line_number


class Dol:
    #HEADER_LEN = 0x100
    __path = None
    # [Section, ...] with length = 18
    __sections = None
    # Bss object
    __bss = None
    __entry_point = None
    def __init__(self, path:Path):
        self.__path = path
        datas = path.read_bytes()

        self.__bss = Bss( int.from_bytes(datas[0xd8:0xdc], "big"), int.from_bytes(datas[0xdc:0xe0], "big") )
        self.__entry_point = int.from_bytes(datas[0xe0:0xe4], "big")

        current_section = 0
        sections = []
        for i in range(18):
            section = Section(
                i, # index
                int.from_bytes(datas[i*4:i*4+4], "big"),           # offset
                int.from_bytes(datas[0x48+i*4:0x48+i*4+4], "big"), # address
                int.from_bytes(datas[0x90+i*4:0x90+i*4+4], "big")) # length

            if section.is_used():
                if i == 7: current_section = 0

                section.set_datas(datas[section.offset():section.offset()+section.length()])
                section.set_name( f".text{current_section}" if i < 7 else f".data{current_section}" )

                current_section += 1
            sections.append(section)
        # Make a tuple to lock from sorting
        self.__sections = tuple(sections)
    def __str__(self):
        'Print a table with each sections from 0 to 17.'
        str_buffer = f"Entry point: {self.__entry_point:08x}\n\n|"
        str_buffer += "-"*50 + "|\n| Section | Offset   | Address  | Length   | Used  |\n|" + "-"*9 + ("|"+"-"*10)*3 + "|" + "-"*7 + "|\n"
        for section in self.__sections:
            str_buffer += section.format_raw()
        return str_buffer + "|"+"-"*50+f"|\n\n{self.__bss.format()}"
    def __get_used_sections(self): return [section for section in self.__sections if section.is_used()]
    def __get_merged_mapped_memory(self):
        """
        Get sorted intervals where there is datas or text.
        return [MemoryObject, ...]
        * Merged and sorted
        private [Section, ...]
        * Don't overlap, section >= 1
        """
        memory_objects = [section.to_memory_object() for section in self.__get_used_sections()]
        memory_objects.sort(key=lambda x:x.address())

        merged_intervals = [memory_objects[0]]
        for memory_object in memory_objects[1:]:
            if merged_intervals[-1].end_address() == memory_object.address():
                merged_intervals[-1].set_end_address( memory_object.end_address() )
            else:
                merged_intervals.append(memory_object)
        return merged_intervals
    def resolve_img2virtual(self, offset:int):
        """
        input: dol_absolute_offset
        return virtual_memory_address
        """
        memory_address = None
        for section in self.__sections:
            if section.is_used():
                virtual_address = section.resolve_img2virtual(offset)
                if virtual_address is not None:
                    return virtual_address
        raise InvalidImgOffsetError(f"Error - Invalid dol image offset: {offset:08x}")
    def resolve_virtual2img(self, address:int):
        """
        input: virtual_memory_address
        return dol_absolute_offset
        """
        for section in self.__sections:
            if section.is_used():
                offset = section.resolve_virtual2img(address)
                if offset is not None:
                    return offset
        raise InvalidVirtualAddressError(f"Error - Not found in dol initial sections: {address:08x}")
    def stats(self):
        # https://www.gc-forever.com/yagcd/chap4.html#sec4
        # system:      0x80000000 -> 0x80003100
        # available:   0x80003100 -> 0x81200000
        # apploader:   0x81200000 -> 0x81300000
        # Bootrom/IPL: 0x81300000 -> 0x81800000

        # Now we have to generate a memory map with splited bss and empty spaces
        # [ [section_name, beg_addr, end_addr, length], ... ]
        memory_objects = [
            MemoryObject(0x80000000, SectionType.SYS, "System",      length=0x3100),
            MemoryObject(0x81200000, SectionType.SYS, "Apploader",   length=0x100000),
            MemoryObject(0x81300000, SectionType.SYS, "Bootrom/IPL", length=0x500000)] + self.__get_used_sections()

        splited = self.__bss.split(memory_objects)
        if splited is not None:
            memory_objects += splited

        # We search now unmapped program space
        memory_objects += MemoryObject(0x80003100, SectionType.UNMAPPED, "Empty", end_address=0x81200000) - memory_objects

        memory_objects.sort(key=lambda x: x.address())
        str_buffer = "\n|"+"-"*46+"|\n| Section     | beg_addr | end_addr | length   |\n|" + "-"*13 + ("|"+"-"*10)*3 + "|\n"
        for memory_object in memory_objects:
            str_buffer += str(memory_object)+"\n"
        print(f"{self}{str_buffer}|"+"-"*46+"|")
    def extract(self, filename:str, section_index:int, output_path:Path):
        if section_index > 17:
            raise Exception("Error - Section index has to be in 0 - 17")

        output_path.write_bytes(self.__sections[section_index].datas())
    def analyse_action_replay(self, action_replay_list:list):
        merged_intervals = self.__get_merged_mapped_memory()

        overlaps_list = get_overlapping_arcodes(action_replay_list)

        # Get unmapped groups splited by sections intervals:
        # each group contains intervals to patch grouped by data sections to add
        unmapped_memory_objects = get_unmapped_intervals(merged_intervals, action_replay_list)

        if overlaps_list is not None:
            str_buffer = "Found overlapping ARCodes:\n"
            str_buffer += "|"+"-"*127+"|\n| Line     | ActionReplayCode1 | beg_addr | end_addr | length   | Line     | ActionReplayCode2 | beg_addr | end_addr | length   |\n|" + ("-"*10 + "|" + "-"*19 + ("|"+"-"*10)*3 + "|")*2 + "\n"
            for [arcode0, arcode1] in overlaps_list:
                str_buffer += str(arcode0)[-1] + str(arcode1) + "\n"
            print(str_buffer+"|"+"-"*127+"|")
        else:
            print(f"No overlapping ARCodes found.")

        if unmapped_memory_objects is not None:
            str_buffer = "\nUnmapped virtual addresses intervals used by ARCodes:\n"+"|"+"-"*32+"|\n| beg_addr | end_addr | length   |\n"+("|"+"-"*10)*3 +"|\n"
            for unmapped_memory_object in unmapped_memory_objects:
                unmapped_memory_object.align()
                str_buffer += f"| {unmapped_memory_object.address():08x} | {unmapped_memory_object.end_address():08x} | {unmapped_memory_object.length():08x} |\n"
            print(str_buffer+"|"+"-"*32+"|")
            print("Use -par file.dol -ini arcodes.ini -o output.dol -sr to remap sections and allow complete processing of the ARCodes in this ini file. Else the patching process will be interupted for out of dol ARCodes.")
        else:
            print(f"No out of sections ARCodes found.\n")
    def patch_memory_objects(self, output_path:Path, memory_objects:list):
        """
        input: [MemoryObject, ... ]
        return True
        raise SectionsOverflowError if part of the bytecode is out of the existing sections
        raise InvalidVirtualAddressError if the base virtual address is out of the existing sections
        """
        sections = self.__get_used_sections()
        sections.sort(key=lambda x: x.address())
        def split_and_patch(sections:list, memory_object:MemoryObject):
            """
            When patching a section we could overflow on the next section or in the previous.
            input: ActionReplayCode
            return True
            raise SectionsOverflowError if part of the bytecode is out of the existing sections
            raise InvalidVirtualAddressError if the base virtual address is out of the existing sections
            """
            for section in sections:
                try:
                    # Intersection
                    if not memory_object & section: continue
                    
                    # Split left_interval, in, right_interval
                    splited = memory_object / section

                    if IntervalDiv.LEFT in splited:
                        split_and_patch(sections, splited[IntervalDiv.LEFT])

                    logging.debug(f"----> offset:{section.offset() + splited[IntervalDiv.IN].address() - section.address():08x} val:{splited[IntervalDiv.IN].datas().hex()}")
                    section.update_datas( splited[IntervalDiv.IN] )

                    if IntervalDiv.RIGHT in splited:
                        split_and_patch(sections, splited[IntervalDiv.RIGHT])

                    return True
                except InvalidVirtualAddressError:
                    raise SectionsOverflowError(f"Error - Value Overflow in an inexistant dol initial section: {memory_object.address():08x}:{memory_object.datas().hex()}")
            raise InvalidVirtualAddressError(f"Error - Not found in dol initial sections: {memory_object.address():08x}:{memory_object.end_address():08x}")
        
        for memory_object in memory_objects:
            logging.debug(f"Processing {memory_object.name()} address:{memory_object.address():08x}")
            split_and_patch(sections, memory_object)
        self.__save(output_path)
    def remap_sections(self, action_replay_list:list):
        merged_intervals = self.__get_merged_mapped_memory()
        unmapped_memory_objects = get_unmapped_intervals(merged_intervals, action_replay_list)
        
        if unmapped_memory_objects is None:
            return True

        text_sections = []
        data_sections = []
        for section in self.__sections:
            if section.is_used():
                section.set_offset(0)
                section.set_index(None)
                if section.type() == SectionType.TEXT:
                    text_sections.append(section)
                else:
                    data_sections.append(section)
        self.__sections = None

        if len(unmapped_memory_objects) + len(data_sections) > 11:
            raise Exception("Error - Not enought empty data sections available for remapping.")

        for unmapped_memory_object in unmapped_memory_objects:
            unmapped_memory_object.align()
            new_section = Section(None, 0, unmapped_memory_object.address(), unmapped_memory_object.length(), section_type=SectionType.UNMAPPED)
            new_section.set_datas( bytearray(b"\x00" * new_section.length()) )
            data_sections.append( new_section )

        text_sections.sort(key=lambda x: x.address())
        data_sections.sort(key=lambda x: x.address())

        sections = []
        current_offset = 0x100
        i = 0
        for text_section in text_sections:
            sections.append( text_section )
            text_section.set_index(i)
            text_section.set_offset(current_offset)
            text_section.set_type(SectionType.TEXT)
            current_offset += text_section.length()
            i += 1
        while i < 7:
            sections.append( Section(i, 0, 0, 0) )
            i += 1
        for data_section in data_sections:
            sections.append( data_section )
            data_section.set_index(i)
            data_section.set_offset(current_offset)
            data_section.set_type(SectionType.DATA)
            current_offset += data_section.length()
            i += 1
        while i < 18:
            sections.append( Section(i, 0, 0, 0) )
            i += 1
        self.__sections = tuple(sections)
    def __save(self, output_path:Path):
        offsets = b""
        addresses = b""
        lengths = b""
        for section in self.__sections:
            offsets += section.offset().to_bytes(4, "big")
            addresses += section.address().to_bytes(4, "big")
            lengths += section.length().to_bytes(4, "big")
        datas = offsets + addresses + lengths +\
            self.__bss.address().to_bytes(4, "big") + self.__bss.length().to_bytes(4, "big") +\
            self.__entry_point.to_bytes(4, "big")
        datas = datas.ljust(0x100, b"\x00")
        for section in sorted(self.__sections, key=lambda x: x.offset()):
            if section.is_used():
                if len(datas) != section.offset():
                    raise InvalidSectionOffsetError(f"Error - Section {section.index()} has an offset that does'nt match the previous datas length.")
                if len(section.datas()) != section.length():
                    raise Exception(f"Error - Invalid datas length.")
                datas += section.datas()
        output_path.write_bytes(datas)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='dol file format utilities - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('-o', '--output-path', type=str, help='-o path: output path.', default=None)
    parser.add_argument('-ini', '--ini-path', type=str, help='-ini path: ini path.', default=None)
    parser.add_argument('-sr', '--sections-remap', action='store_true', help="-sr: remap the data sections of the dol to allow full ARCodes ini"
        " file processing.", default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-v2i', '--virtual2image', type=str, help="-v2i source.dol virtual_address: Translate a virtual address into "
        "a dol offset if this was originaly mapped from data or text. virtual_address has to be in hexadecimal: 80003100.")
    group.add_argument('-i2v', '--image2virtual', type=str, help="-i2v source.dol dol_offset: Translate a dol offset to a virtual ad"
        "dress mapped from data or text. dol_offset has to be in hexadecimal: 2000.")
    group.add_argument('-s', '--stats', action='store_true', help="-s source.dol: Get stats about entry point, sections, bss and unu"
        "sed virtual address space.")
    group.add_argument('-e', '--extract', type=int, help="-e source.dol section_index [-o output_path]: Extract a section. index mus"
        "t be between 0 and 17")
    group.add_argument('-aar', '--analyse-action-replay', action='store_true', help="-aar source.dol action_replay.ini: Analyse an i"
        "ni file containing a list of [write] directives to show unmapped sections to add for processing all ARCodes including thoos"
        "e who are in inexistant sections. Handle only ARCodes beginning with [00, 01, 02, 03, 04, 05].")
    group.add_argument('-par', '--patch-action-replay', action='store_true', help="-par source.dol -ini action_replay.ini [-o output"
        "_path] [-sr]: Patch initialised data inside the dol with an ini file containing a list of [write] directives. Handle only A"
        "RCodes beginning with [00, 01, 02, 03, 04, 05]. If -sr is specified then add or update .data sections to allow full ini proc"
        "essing.")
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
        virtual_address = int(args.virtual2image, 16)
        try:
            offset = dol.resolve_virtual2img(virtual_address)
            print(f"Virtual address {virtual_address:08x} is at dol offset {offset:08x}")
        except InvalidVirtualAddressError:
            print("This virtual address is not in the dol.")
    elif args.image2virtual:
        offset = int(args.image2virtual, 16)
        try:
            virtual_address = dol.resolve_img2virtual(offset)
            print(f"Dol offset {offset:08x} is at virtual address {virtual_address:08x}")
        except InvalidImgOffsetError:
            print("This dol offset is invalid.")
    elif args.stats:
        dol.stats()
    elif args.extract:
        logging.info("### Extract section")
        index = args.extract

        section_type = "text" if index < 7 else "data"
        output_path = Path(args.output_path) if args.output_path is not None else Path(f"{p_input.name}_{section_type}{index}")
        logging.info(f"Extracting section {index} in file {output_path}...")

        dol.extract(p_input.name, index, output_path)
    elif args.analyse_action_replay:
        logging.info("### Analyse Action Replay ini file")
        if args.ini_path is None:
            raise Exception("Error - Action Replay ini file has to be specified.")
        action_replay_ini_path = Path(args.ini_path)
        if not action_replay_ini_path.is_file():
            raise Exception("Error - Invalid action replay ini file path.")
        dol.analyse_action_replay(parse_action_replay_ini(action_replay_ini_path))
    elif args.patch_action_replay:
        logging.info("### Patch dol using Action Replay ini file")
        if args.ini_path is None:
            raise Exception("Error - Action Replay ini file has to be specified.")
        action_replay_ini_path = Path(args.ini_path)
        if not action_replay_ini_path.is_file():
            raise Exception("Error - Invalid action replay ini file path.")

        if not args.output_path:
            raise Exception("Error - Output path has to be specified.")
        output_path = Path(args.output_path)
        if output_path.is_file():
            raise Exception(f"Error - Please remove {output_path}.")

        logging.info(f"Patching dol {p_input} in {output_path} using {action_replay_ini_path} ini file...")

        action_replay_list = parse_action_replay_ini(action_replay_ini_path)
        if args.sections_remap != None:
            logging.info(f"Sections remapping using action replay ini file...")
            dol.remap_sections(action_replay_list)

        dol.patch_memory_objects(output_path, action_replay_list)
