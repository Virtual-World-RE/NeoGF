#!/usr/bin/env python3
from configparser import ConfigParser
import logging
from pathlib import Path
import re


__version__ = "0.2.1"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


# raised when the boot.bin DVD magic number is invalid
class InvalidDVDMagicError(Exception): pass
# raised when unpack folder already exist to avoid erasing already existing files
class InvalidUnpackFolderError(Exception): pass
# raised when pack iso already exist to avoid erasing already existing file
class InvalidPackIsoError(Exception): pass
# raised during pack when fst.bin size doesn't match the boot.bin value 
class InvalidFSTSizeError(Exception): pass
# raised during pack when boot.dol size overflow on first file or on FST
class DolSizeOverflowError(Exception): pass
# raised during pack when fst.bin size overflow on first file or on dol
class FstSizeOverflowError(Exception): pass
# raised during pack when FST folder entry has an invalid nextdir id value; this happen when file and folder has been added/removed
class InvalidRootFileFolderCountError(Exception): pass
# raised during pack when FST file entry has a different value than the file being packed; this happen when a file has been edited changing it's size
class InvalidFSTFileSizeError(Exception): pass
# raised during pack when FST dir name is not found in the root folder; this happen when a dir is renamed or removed
class FSTDirNotFoundError(Exception): pass
# raised during pack when FST file name is not found in the root folder; this happen when a file is renamed or removed
class FSTFileNotFoundError(Exception): pass
# raised when using an invalid align
class BadAlignError(Exception): pass
# raised when a system conf entry has an invalid format
class InvalidConfValueError(Exception): pass
# raised when apploader overflow on dol or fst
class ApploaderOverflowError(Exception): pass


def align_top(offset:int, align:int):
    """
    Give the upper rounded offset aligned using the align value.
    input: offset = int
    input: align = int
    return offset = int
    """
    if offset % align == 0: return offset
    return offset + align - (offset % align)


class Fst:
    "Pack FST type enum values."
    TYPE_FILE = 0
    TYPE_DIR = 1


class Node:
    """
    Interface Node used to be herited by File and Folder classes.
    It groups common properties and allow an FST rebuid:
        FST use a base_name block and name offsets relative to it for all
        entries: Files or Folders. So we handle name in this interface.
        name offset will be set during the FstTree.__prepare() after all
        of the three elements are added.
        Also every File and Folder get an ID. This ID is important when
        rebuilding the FST with folders (next dir, parent dir) ...
    Constructor: name = str (file or folder)
    """
    __id = None
    __name = None
    __name_offset = None
    def __init__(self, name:str):
        self.__name = name
    def id(self):             return self.__id
    def name(self):           return self.__name
    def name_offset(self):    return self.__name_offset
    def set_id(self, id:int): self.__id = id
    def set_name_offset(self, name_offset:int): self.__name_offset = name_offset


class File(Node):
    """
    Use a global class attribute TYPE_FILE and store necessary
    informations for formating the FST 12 bytes entry with the
    format "type/name_offset/gcm_offset/size"
    Constructor:
    * name = str
    * size = int
    """
    __type = Fst.TYPE_FILE
    __size = None
    __offset = None
    def __init__(self, name:str, size:int):
        super().__init__(name)
        self.__size = size
    def __str__(self):
        return f"{self.id()};{self.name()};{self.size()};{self.offset()};{self.name_offset()}"
    def type(self):                   return self.__type
    def size(self):                   return self.__size
    def offset(self):                 return self.__offset
    def set_offset(self, offset:int): self.__offset = offset 
    def format(self):
        return self.type().to_bytes(1, "big") + self.name_offset().to_bytes(3, "big") + self.offset().to_bytes(4, "big") + self.size().to_bytes(4, "big")


class Folder(Node):
    """
    Use a global class attribute TYPE_DIR and store necessary
    informations for formating the FST 12 bytes entry with the
    format "type/name_offset/parent_id/next_id". This class is 
    intended to hold the tree with multiple childs and one parent
    only. The next dir is the total number of childs + 1
    Constructor:
    * name = str
    * parent = Node
    """
    __type = Fst.TYPE_DIR
    __parent = None
    __next_dir = None
    __childs = None
    def __init__(self, name:str, parent:Node):
        super().__init__(name)
        self.__parent = parent
        self.__childs = []
    def __str__(self):
        return f"{self.id()};{self.name()};{self.next_dir()};{self.name_offset()}"
    def type(self):                   return self.__type
    def parent(self):                 return self.__parent
    def next_dir(self):               return self.__next_dir
    def childs(self):                 return self.__childs
    def set_next_dir(self, next_dir): self.__next_dir = next_dir
    def add_child(self, node:Node):
        "Search child by name an return existing if found or new if not existing"
        for child in self.__childs:
            if node.name() == child.name():
                return child
        self.__childs.append(node)
        return node
    def format(self):
        return self.type().to_bytes(1, "big") + self.name_offset().to_bytes(3, "big") + self.parent().id().to_bytes(4, "big") + self.next_dir().to_bytes(4, "big")


class FstTree(Fst):
    """
    FstTree is responsible for creating and formating the FST and name_block.
    We store a root Node that is a special Folder.
    Constructor:
    * root_path = Path (the part with folder that are out of the tree)
    * fst_offset = int (to know where is the current min offset before 
        adding the fst and name_block length)
        has to be aligned
    * align = int (It could change in some GCM)
    """
    # When we walk recursivly in a path we don't wan't to add theirs out parents so it allow to stop at the folder we choose as root
    __root_path_length = None
    __root_node = None
    # We start at root-node with id=0
    __current_id = 0
    # We will align this offset to the next available place after new packed file
    __current_file_offset = None
    __align = None
    __fst_block = None
    __name_block = None
    # Used to find min file_offset when fst is at the end of the iso beginning (otherweise we can't know the first available offset)
    __nameblock_length = None
    __user_position = None
    __user_length = None
    # FST high tell if fst is after dol
    __is_fst_last = None
    def __init__(self, root_path:Path, offset:int, is_fst_last:bool, align:int = 4):
        # as said before we don't want to add parents folder that don't are used in the folder we are packing.
        self.__root_path_length = len(root_path.parts)
        self.__root_node = Folder(root_path.name, None)
        self.__align = align
        self.__name_block = b""
        self.__fst_block = b""
        self.__nameblock_length = 0
        self.__current_file_offset = offset
        self.__is_fst_last = is_fst_last
    def __str__(self):
        return self.__to_str(self.__root_node)
    def __to_str(self, node:Node, depth=0):
        """
        Recursive Tree str buffer for debug.
        input: Node (to print childs)
        return tree = str
        """
        result = (depth * "    ") + str(node) +"\n"
        if node.type() == FstTree.TYPE_DIR:
            for child in node.childs():
                result += self.__to_str(child, depth+1)
        return result
    def __get_fst_length(self):
        """
        Needed to know where we can begin to write files.
        return fst_length = int
        """
        self.__generate_nameblock_length()
        return align_top(self.__count_childs(self.__root_node)*12 + 12 + self.__nameblock_length, self.__align)
    def __generate_nameblock_length(self, node:Node = None):
        """
        Recursive walk into the tree to get total name_block length.
        input: None (then it will use node:Node to recurse)
        """
        if node is None:
            node = self.__root_node
        else:
            self.__nameblock_length += len(node.name()) + 1
        if node.type() == FstTree.TYPE_DIR:
            for child in node.childs():
                self.__generate_nameblock_length(child)
    def __prepare(self, node:Node = None):
        """
        Populate recursivly every Nodes with required informations for formating and generate the name_block and fst_block.
        input: None (then it will use node:Node to recurse)
        """
        name_offset = 0
        # For root Node we build the nameblock with null trailing byte
        # For others we build the name_block and update the name_offset
        if node is None:
            node = self.__root_node
        else:
            name_offset = len(self.__name_block)
            self.__name_block += node.name().encode("utf-8")+b"\x00"
        # We set the name_offset, the id, we increment for next walked node
        node.set_name_offset(name_offset)
        node.set_id(self.__current_id)
        self.__current_id += 1
        
        # If it's a directory we have to count childs to set nextdir
        # If it's a file we have to set the offset and add length aligned to it for finding next available offset
        # At the end we add to the fst_block our formated Node
        if node.type() == FstTree.TYPE_DIR:
            node.set_next_dir(self.__current_id + self.__count_childs(node))
            if node == self.__root_node:
                self.__fst_block = b"\x01\x00\x00\x00\x00\x00\x00\x00" + node.next_dir().to_bytes(4, "big")
            else:
                self.__fst_block += node.format()
            for child in node.childs():
                self.__prepare(child)
        else:
            node.set_offset(self.__current_file_offset)
            self.__fst_block += node.format()
            self.__current_file_offset = align_top(self.__current_file_offset + node.size(), self.__align)
    def __count_childs(self, node:Folder):
        """
        Recursivly count total childs of a Node. It is usefull for getting next_dir id.
        input: node = Folder
        return child_count = int
        """
        count = 0
        for child in node.childs():
            if child.type() == FstTree.TYPE_DIR:
                count += self.__count_childs(child)
        return count + len(node.childs())
    def add_node_by_path(self, node_path:Path):
        """
        Add a path with each folder as Folder class and the File as a leaf.
        We take care to set parent and childs for folder and retrieve necessary
        informations from the node_path input:
        * name
        * size
        * parent id & parent->child
        input: path = Path (folder / file)
        """
        parent = self.__root_node
        node = None
        for i in range(self.__root_path_length, len(node_path.parts)-1):
            node = Folder(node_path.parts[i], parent)
            parent = parent.add_child(node)
        if node_path.is_file():
            node = File(node_path.name, node_path.stat().st_size)
        else:
            node = Folder(node_path.name, parent)
        parent.add_child(node)
    def generate_fst(self):
        """
        Generate the FST.
        The hard part Here is that we have to know the result before
        knowing where we can begin to add files.
        """
        if self.__is_fst_last:
            self.__current_file_offset += self.__get_fst_length() # aligned + aligned = aligned
        self.__user_position = self.__current_file_offset
        self.__prepare()
        self.__user_length = self.__current_file_offset - self.__user_position
        return self.__fst_block + self.__name_block
    def user_position(self): return self.__user_position
    def user_length(self):   return self.__user_length


class BootBin:
    """
    BootBin describe the Disc Header "boot.bin" file at the beginning of 
    the GCM/iso. It groups all operations related to the boot.bin system 
    file extracted in sys/boot.bin. Using this class avoid errors on offsets
    and makes it easier to get or set values.
    Constructor:
    * datas = bytes or bytearray if edit of the boot.bin is needed.
    """
    LEN = 0x440
    DOLOFFSET_OFFSET = 0x420
    FSTOFFSET_OFFSET = 0x424
    FSTLEN_OFFSET = 0x428
    FSTMAXLEN_OFFSET = 0x42c
    __data = None
    def __init__(self, data:bytes): self.__data = data
    def data(self):               return self.__data
    def make_mut(self):           self.__data = bytearray(self.__data)
    def game_code(self):          return self.__data[:4].decode("ascii")
    def maker_code(self):         return self.__data[4:6].decode("ascii")
    def disc_number(self):        return int.from_bytes(self.__data[6:7], 'big')
    def game_version(self):       return int.from_bytes(self.__data[7:8], 'big')
    def audio_streaming(self):    return int.from_bytes(self.__data[8:9], 'big')
    def stream_buffer_size(self): return int.from_bytes(self.__data[9:0xa], 'big')
    def dvd_magic(self):          return self.__data[0x1c:0x20]
    def game_name(self):          return self.__data[0x20:0x60].split(b"\x00")[0].decode("utf-8")
    def dol_offset(self):         return int.from_bytes(self.__data[BootBin.DOLOFFSET_OFFSET:BootBin.DOLOFFSET_OFFSET+4],"big")
    def fst_offset(self):         return int.from_bytes(self.__data[BootBin.FSTOFFSET_OFFSET:BootBin.FSTOFFSET_OFFSET+4],"big")
    def fst_len(self):            return int.from_bytes(self.__data[BootBin.FSTLEN_OFFSET:BootBin.FSTLEN_OFFSET+4],"big")
    def fst_max_len(self):        return int.from_bytes(self.__data[BootBin.FSTMAXLEN_OFFSET:BootBin.FSTMAXLEN_OFFSET+4],"big")
    def user_position(self):      return int.from_bytes(self.__data[0x434:0x438],"big")
    def user_length(self):        return int.from_bytes(self.__data[0x438:0x43c],"big")
    def set_game_code(self, game_code:str):
        self.__data[:4] = bytes(game_code, "ascii")
    def set_maker_code(self, maker_code:str):
        self.__data[4:6] = bytes(maker_code, "ascii")
    def set_disc_number(self, disc_number:int):
        self.__data[6:7] = disc_number.to_bytes(1, "big")
    def set_game_version(self, game_version:int):
        self.__data[7:8] = game_version.to_bytes(1, "big")
    def set_audio_streaming(self, audio_streaming:int):
        self.__data[8:9] = audio_streaming.to_bytes(1, "big")
    def set_stream_buffer_size(self, stream_buffer_size:int):
        self.__data[9:0xa] = stream_buffer_size.to_bytes(1, "big")
    def set_dvd_magic(self, dvd_magic:int):
        self.__data[0x1c:0x20] = dvd_magic.to_bytes(4, "big")
    def set_game_name(self, game_name:int):
        self.__data[0x20:0x60] = bytes(game_name, "utf-8").ljust(0x40, b"\x00")
    def set_dol_offset(self, offset:int):
        self.__data[BootBin.DOLOFFSET_OFFSET:BootBin.DOLOFFSET_OFFSET+4] = offset.to_bytes(4, "big")
    def set_fst_offset(self, offset:int):
        self.__data[BootBin.FSTOFFSET_OFFSET:BootBin.FSTOFFSET_OFFSET+4] = offset.to_bytes(4, "big")
    def set_fst_len(self, length:int):
        self.__data[BootBin.FSTLEN_OFFSET:BootBin.FSTLEN_OFFSET+4] = length.to_bytes(4, "big")
    def set_fst_max_len(self, length:int):
        self.__data[BootBin.FSTMAXLEN_OFFSET:BootBin.FSTMAXLEN_OFFSET+4] = length.to_bytes(4, "big")
    def set_user_position(self, user_position:int):
        self.__data[0x434:0x438] = user_position.to_bytes(4, "big")
    def set_user_length(self, user_length:int):
        self.__data[0x438:0x43c] = user_length.to_bytes(4, "big")


class Bi2Bin:
    """
    Bi2Bin describe the Disc Header Information "bi2.bin" file at the 
    beginning of the GCM/iso after boot.bin. It groups all operations
    related to the bi2.bin system file extracted in sys/bi2.bin. Using 
    this class avoid errors on offsets and makes it easier to get or set 
    values.
    Constructor:
    * datas = bytes or bytearray if edit of the bi2.bin is needed.
    """
    LEN = 0x2000
    __data = None
    def __init__(self, data:bytes): self.__data = data
    def data(self):                 return self.__data
    def make_mut(self):             self.__data = bytearray(self.__data)
    def debug_monitor_size(self):     return int.from_bytes(self.__data[:4], "big")
    def simulated_memory_size(self):  return int.from_bytes(self.__data[4:8], "big")
    def argument_offset(self):        return int.from_bytes(self.__data[8:12], "big")
    def debug_flag(self):             return int.from_bytes(self.__data[12:16], "big")
    def track_location(self):         return int.from_bytes(self.__data[16:20], "big")
    def track_size(self):             return int.from_bytes(self.__data[20:24], "big")
    def country_code(self):           return int.from_bytes(self.__data[24:28], "big")
    def total_disc(self):             return int.from_bytes(self.__data[28:32], "big")
    def long_file_name_support(self): return int.from_bytes(self.__data[32:36], "big")
    def dol_limit(self):              return int.from_bytes(self.__data[40:44], "big")
    def set_debug_monitor_size(self, debug_monitor_size:int):
        self.__data[:4] = debug_monitor_size.to_bytes(4, "big")
    def set_simulated_memory_size(self, simulated_memory_size:int):
        self.__data[4:8] = simulated_memory_size.to_bytes(4, "big")
    def set_argument_offset(self, argument_offset:int):
        self.__data[8:12] = argument_offset.to_bytes(4, "big")
    def set_debug_flag(self, debug_flag:int):
        self.__data[12:16] = debug_flag.to_bytes(4, "big")
    def set_track_location(self, track_location:int):
        self.__data[16:20] = track_location.to_bytes(4, "big")
    def set_track_size(self, track_size:int):
        self.__data[20:24] = track_size.to_bytes(4, "big")
    def set_country_code(self, country_code:int):
        self.__data[24:28] = country_code.to_bytes(4, "big")
    def set_total_disc(self, total_disc:int):
        self.__data[28:32] = total_disc.to_bytes(4, "big")
    def set_long_file_name_support(self, long_file_name_support:int):
        self.__data[32:36] = long_file_name_support.to_bytes(4, "big")
    def set_dol_limit(self, dol_limit:int):
        self.__data[40:44] = dol_limit.to_bytes(4, "big")
        

class ApploaderImg:
    __data = None
    def __init__(self, data:bytes): self.__data = data
    def data(self):         return self.__data
    def len(self):          return len(self.__data)
    def make_mut(self):     self.__data = bytearray(self.__data)
    def version(self):      return self.__data[:0x10].split(b"\x00")[0].decode("ascii")
    def entry_point(self):  return int.from_bytes(self.__data[0x10:0x14], "big")
    def size(self):         return int.from_bytes(self.__data[0x14:0x18], "big")
    def trailer_size(self): return int.from_bytes(self.__data[0x18:0x1c], "big")
    def set_version(self, version:int):           self.__data[:0x10]     = bytes(version, "ascii").ljust(0x10, b"\x00")
    def set_entry_point(self, entry_point:int):   self.__data[0x10:0x14] = entry_point.to_bytes(4, "big")
    def set_size(self, size:int):                 self.__data[0x14:0x18] = size.to_bytes(4, "big")
    def set_trailer_size(self, trailer_size:int): self.__data[0x18:0x1c] = trailer_size.to_bytes(4, "big")


class Dol:
    "Dol is used to find the dol size and group data adding meaning to hex values and allowing to get it's size."
    HEADER_LEN = 0x100
    HEADER_SECTIONLENTABLE_OFFSET = 0x90
    def get_dol_len(self, dolheader_data:bytes):
        """
        Get total length using the sum of the 18 sections length and dol header length.
        * input: dolheader_data = bytes
        * return dol_len = int
        """
        dol_len = Dol.HEADER_LEN
        for i in range(18):
            dol_len += int.from_bytes(dolheader_data[Dol.HEADER_SECTIONLENTABLE_OFFSET+i*4:Dol.HEADER_SECTIONLENTABLE_OFFSET+(i+1)*4], "big")
        return dol_len


class Gcm:
    """
    Gcm handle all operations needed by the command parser.
    File format informations: https://sudonull.com/post/68549-Gamecube-file-system-device
    """
    APPLOADER_HEADER_LEN = 0x20
    APPLOADER_OFFSET = 0x2440
    APPLOADERLEN_OFFSET = 0x2454
    DVD_MAGIC = b"\xC2\x33\x9F\x3D"
    __bootbin = None # Disc header
    __bi2bin = None  # Disc header Information
    __apploaderimg = None
    __hex_pattern = re.compile("^0x[0-9a-fA-F]+$")
    def __save_conf(self, sys_path:Path):
        "Read boot.bin and bi2.bin and save theirs conf in sys/system.conf."

        config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
        config.optionxform = str # makes options case sensitive
        config.add_section("Default")
        config.set("Default", "# Documentation available here: https://github.com/Virtual-World-RE/NeoGF/blob/main/gcmtool/README.md#syssytemconf")
        config.set("Default", "boot.bin_section", "disabled")
        config.set("Default", "bi2.bin_section", "disabled")
        config.set("Default", "apploader.img_section", "disabled")

        config.add_section("boot.bin")
        config.set("boot.bin", "GameCode",         self.__bootbin.game_code()) # 4 bytes ASCII
        config.set("boot.bin", "MakerCode",        self.__bootbin.maker_code()) # 2 bytes ASCII
        config.set("boot.bin", "DiscNumber",       str(self.__bootbin.disc_number())) # 0-98
        config.set("boot.bin", "GameVersion",      str(self.__bootbin.game_version())) # 0-99
        config.set("boot.bin", "AudioStreaming",   str(self.__bootbin.audio_streaming())) # 0 or 1 flag
        config.set("boot.bin", "StreamBufferSize", str(self.__bootbin.stream_buffer_size())) # 0-15
        config.set("boot.bin", "DVDMagic",         "0x" + self.__bootbin.dvd_magic().hex())
        config.set("boot.bin", "GameName",         self.__bootbin.game_name()) # 64 bytes
        config.set("boot.bin", "DolOffset",        f"auto")
        config.set("boot.bin", "FstOffset",        f"auto")
        config.set("boot.bin", "FstLen",           f"auto")
        config.set("boot.bin", "FstMaxLen",        f"auto")
        config.set("boot.bin", "UserPosition",     f"auto")
        config.set("boot.bin", "UserLength",       f"auto")
        

        config.add_section("bi2.bin")
        config.set("bi2.bin", "DebugMonitorSize",    f"0x{self.__bi2bin.debug_monitor_size():x}")
        config.set("bi2.bin", "SimulatedMemorySize", f"0x{self.__bi2bin.simulated_memory_size():x}")
        config.set("bi2.bin", "ArgumentOffset",      f"0x{self.__bi2bin.argument_offset():x}")
        config.set("bi2.bin", "DebugFlag",           str(self.__bi2bin.debug_flag()))
        config.set("bi2.bin", "TrackLocation",       f"0x{self.__bi2bin.track_location():x}")
        config.set("bi2.bin", "TrackSize",           f"0x{self.__bi2bin.track_size():x}")
        config.set("bi2.bin", "CountryCode",         str(self.__bi2bin.country_code())) # 0, 1, 2, 4
        config.set("bi2.bin", "TotalDisc",           str(self.__bi2bin.total_disc())) # 1-99
        config.set("bi2.bin", "LongFileNameSupport", str(self.__bi2bin.long_file_name_support())) # 0, 1
        config.set("bi2.bin", "DolLimit",            f"0x{self.__bi2bin.dol_limit():x}")

        config.add_section("apploader.img")
        config.set("apploader.img", "Version",     self.__apploaderimg.version())
        config.set("apploader.img", "EntryPoint",  f"0x{self.__apploaderimg.entry_point():x}")
        config.set("apploader.img", "Size",        f"0x{self.__apploaderimg.size():x}")
        config.set("apploader.img", "TrailerSize", f"0x{self.__apploaderimg.trailer_size():x}")

        with (sys_path / "system.conf").open("w") as conf_file:
            config.write(conf_file)
        logging.info("sys/sytem.conf saved.")
    def __load_conf(self, sys_path:Path, get_conf_values:bool = False):
        "Patch boot.bin, bi2.bin and apploader.img with the conf in sys/system.conf if Default section status is enabled."
        config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
        config.optionxform = str # makes options case sensitive
        config.read(sys_path / "system.conf")

        if config["Default"]["boot.bin_section"].lower() not in ["enabled", "disabled"]:
            raise InvalidConfValueError("Error - Invalid [Default][boot.bin_section]: must be enabled or disabled.")
        if config["Default"]["bi2.bin_section"].lower() not in ["enabled", "disabled"]:
            raise InvalidConfValueError("Error - Invalid [Default][bi2.bin_section]: must be enabled or disabled.")
        if config["Default"]["apploader.img_section"].lower() not in ["enabled", "disabled"]:
            raise InvalidConfValueError("Error - Invalid [Default][apploader.img_section]: must be enabled or disabled.")

        def check_numeric_format(config:ConfigParser, conf_list:list):
            for conf in conf_list:
                if not config[conf[0]][conf[1]].isnumeric():
                    raise InvalidConfValueError(f"Error - Invalid [{conf[0]}][{conf[1]}]: must be numeric - 1234.")
        def check_hex_format(config:ConfigParser, conf_list:list):
            for conf in conf_list:
                if conf[2] and config[conf[0]][conf[1]] == "auto":
                    continue
                if not self.__hex_pattern.fullmatch(config[conf[0]][conf[1]]):
                    raise InvalidConfValueError(f"Error - Invalid [{conf[0]}][{conf[1]}]: must be hex - 0xabcdef.")

        check_numeric_format(config, [
            ("boot.bin", "DiscNumber"),
            ("boot.bin", "GameVersion"),
            ("boot.bin", "StreamBufferSize"),
            ("bi2.bin", "DebugFlag"),
            ("bi2.bin", "TotalDisc")])

        check_hex_format(config, [
            ("boot.bin", "DVDMagic",           False),
            ("boot.bin", "DolOffset",          True),
            ("boot.bin", "FstOffset",          True),
            ("boot.bin", "FstLen",             True),
            ("boot.bin", "FstMaxLen",          True),
            ("boot.bin", "UserPosition",       True),
            ("boot.bin", "UserLength",         True),
            ("bi2.bin", "DebugMonitorSize",    False),
            ("bi2.bin", "SimulatedMemorySize", False),
            ("bi2.bin", "ArgumentOffset",      False),
            ("bi2.bin", "TrackLocation",       False),
            ("bi2.bin", "TrackSize",           False),
            ("bi2.bin", "DolLimit",            False),
            ("apploader.img", "EntryPoint",    False),
            ("apploader.img", "Size",          False),
            ("apploader.img", "TrailerSize",   False)])
        
        self.__bootbin.make_mut()
        self.__bi2bin.make_mut()
        self.__apploaderimg.make_mut()

        conf_value_dol_offset = None
        conf_value_fst_offset = None
        conf_value_fst_len = 0
        conf_value_fst_max_len = None
        conf_value_user_position = None
        conf_value_user_length = None

        if config["Default"]["boot.bin_section"].lower() == "enabled":
            if len(config["boot.bin"]["GameCode"]) != 4:
                raise InvalidConfValueError("Error - Invalid [boot.bin][GameCode]: must be str with length = 4.")
            self.__bootbin.set_game_code( config["boot.bin"]["GameCode"] )
            
            if len(config["boot.bin"]["MakerCode"]) != 2:
                raise InvalidConfValueError("Error - Invalid [boot.bin][MakerCode]: must be str with length = 2.")
            self.__bootbin.set_maker_code( config["boot.bin"]["MakerCode"] )
            
            disc_number = int(config["boot.bin"]["DiscNumber"])
            if disc_number > 98:
                raise InvalidConfValueError("Error - Invalid [boot.bin][DiscNumber]: must be int with value < 99.")
            self.__bootbin.set_disc_number( disc_number )

            game_version = int(config["boot.bin"]["GameVersion"])
            if game_version > 99:
                raise InvalidConfValueError("Error - Invalid [boot.bin][GameVersion]: must be int with value < 100.")
            self.__bootbin.set_game_version( game_version )

            if config["boot.bin"]["AudioStreaming"] not in ["0", "1"]:
                raise InvalidConfValueError("Error - Invalid [boot.bin][AudioStreaming]: this flag must be 0 or 1.")
            self.__bootbin.set_audio_streaming( int(config["boot.bin"]["AudioStreaming"]) )

            stream_buffer_size = int(config["boot.bin"]["StreamBufferSize"])
            if stream_buffer_size > 15:
                raise InvalidConfValueError("Error - Invalid [boot.bin][StreamBufferSize]: must be int with value between 0 and 15.")
            self.__bootbin.set_stream_buffer_size( stream_buffer_size )

            if len(config["boot.bin"]["DVDMagic"]) != 10:
                raise InvalidConfValueError("Error - Invalid [boot.bin][DVDMagic]: must be 8 hex digits begining with 0x.")
            self.__bootbin.set_dvd_magic( int(config["boot.bin"]["DVDMagic"], 16) )
            
            if len(config["boot.bin"]["GameName"]) > 64:
                raise InvalidConfValueError("Error - Invalid [boot.bin][GameName]: must be str with length < 64.")
            self.__bootbin.set_game_name( config["boot.bin"]["GameName"] )

            if config["boot.bin"]["DolOffset"] != "auto":
                dol_offset = int(config["boot.bin"]["DolOffset"], 16)
                if dol_offset > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][DolOffset]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_dol_offset( dol_offset )
                conf_value_dol_offset = dol_offset

            if config["boot.bin"]["FstOffset"] != "auto":
                fst_offset = int(config["boot.bin"]["FstOffset"], 16)
                if fst_offset > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][FstOffset]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_fst_offset( fst_offset )
                conf_value_fst_offset = fst_offset

            if config["boot.bin"]["FstLen"] != "auto":
                fst_len = int(config["boot.bin"]["FstLen"], 16)
                if fst_len > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][FstLen]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_fst_len( fst_len )
                conf_value_fst_len = fst_len

            if config["boot.bin"]["FstMaxLen"] != "auto":
                fst_max_len = int(config["boot.bin"]["FstMaxLen"], 16)
                if fst_max_len > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][FstMaxLen]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_fst_max_len( fst_max_len )
                conf_value_fst_max_len = fst_max_len
        
            if config["boot.bin"]["UserPosition"] != "auto":
                user_position = int(config["boot.bin"]["UserPosition"], 16)
                if user_position > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][UserPosition]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_user_position( user_position )
                conf_value_user_position = user_position
            
            if config["boot.bin"]["UserLength"] != "auto":
                user_length = int(config["boot.bin"]["UserLength"], 16)
                if user_length > 0xffffffff:
                    raise InvalidConfValueError("Error - Invalid [boot.bin][UserLength]: must be auto or unsigned hex value with length < 5 bytes.")
                self.__bootbin.set_user_length( user_length )
                conf_value_user_length = user_length

        if config["Default"]["bi2.bin_section"].lower() == "enabled":
            debug_monitor_size = int(config["bi2.bin"]["DebugMonitorSize"], 16)
            if debug_monitor_size > 0xffffffff or debug_monitor_size & 31:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][DebugMonitorSize]: must be hex value with length < 5 bytes and aligned to 32.")
            self.__bi2bin.set_debug_monitor_size( debug_monitor_size )

            simulated_memory_size = int(config["bi2.bin"]["SimulatedMemorySize"], 16)
            if simulated_memory_size > 0xffffffff or simulated_memory_size & 31:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][SimulatedMemorySize]: must be hex value with length < 5 bytes and aligned to 32.")
            self.__bi2bin.set_simulated_memory_size( simulated_memory_size )

            argument_offset = int(config["bi2.bin"]["ArgumentOffset"], 16)
            if argument_offset > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][ArgumentOffset]: must be hex value with length < 5 bytes.")
            self.__bi2bin.set_argument_offset( argument_offset )

            debug_flag = int(config["bi2.bin"]["DebugFlag"])
            if debug_flag > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][DebugFlag]: must be hex value with length < 5 bytes.")
            self.__bi2bin.set_debug_flag( debug_flag )

            track_location = int(config["bi2.bin"]["TrackLocation"], 16)
            if track_location > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][TrackLocation]: must be hex value with length < 5 bytes.")
            self.__bi2bin.set_track_location( track_location )

            track_size = int(config["bi2.bin"]["TrackSize"], 16)
            if track_size > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][TrackSize]: must be hex value with length < 5 bytes.")
            self.__bi2bin.set_track_size( track_size )

            if config["bi2.bin"]["CountryCode"] not in ["0", "1", "2", "4"]:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][CountryCode]: must have 0, 1, 2 or 4 value.")
            self.__bi2bin.set_country_code( int(config["bi2.bin"]["CountryCode"]) )

            if int(config["bi2.bin"]["TotalDisc"]) > 99:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][TotalDisc]: must between 1 and 99.")
            self.__bi2bin.set_total_disc( int(config["bi2.bin"]["TotalDisc"], 16) )

            if config["bi2.bin"]["LongFileNameSupport"] not in ["0", "1"]:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][LongFileNameSupport]: must be 0 or 1.")
            self.__bi2bin.set_long_file_name_support( int(config["bi2.bin"]["LongFileNameSupport"]) )

            dol_limit = int(config["bi2.bin"]["DolLimit"], 16)
            if dol_limit > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [bi2.bin][DolLimit]: must be hex value with length < 5 bytes.")
            self.__bi2bin.set_dol_limit( dol_limit )

        if config["Default"]["apploader.img_section"].lower() == "enabled":
            version = config["apploader.img"]["Version"]
            if len(version) > 10:
                raise InvalidConfValueError("Error - Invalid [apploader.img][Version]: must be 16 byte ascii string.")
            self.__apploaderimg.set_version( version )

            entry_point = int(config["apploader.img"]["EntryPoint"], 16)
            if entry_point > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [apploader.img][EntryPoint]: must be hex value with length < 5 bytes.")
            self.__apploaderimg.set_entry_point( entry_point )
            
            size = int(config["apploader.img"]["Size"], 16)
            if size > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [apploader.img][Size]: must be hex value with length < 5 bytes.")
            self.__apploaderimg.set_size( size )
            
            trailer_size = int(config["apploader.img"]["TrailerSize"], 16)
            if trailer_size > 0xffffffff:
                raise InvalidConfValueError("Error - Invalid [apploader.img][TrailerSize]: must be hex value with length < 5 bytes.")
            self.__apploaderimg.set_trailer_size( trailer_size )

        (sys_path / "boot.bin").write_bytes(self.__bootbin.data())
        (sys_path / "bi2.bin").write_bytes(self.__bi2bin.data())
        (sys_path / "apploader.img").write_bytes(self.__apploaderimg.data())

        logging.info("sys/sytem.conf loaded.")

        if get_conf_values:
            return (
                conf_value_dol_offset,
                conf_value_fst_offset,
                conf_value_fst_len,
                conf_value_fst_max_len,
                conf_value_user_position,
                conf_value_user_length
            )
    def __get_min_file_offset(self, fstbin_data:bytes):
        "Get the min file offset to check if there is an overflow."
        min_offset = None
        for i in range(2, int.from_bytes(fstbin_data[8:12], "big")):
            if int.from_bytes(fstbin_data[i*12:i*12+1], "big") == FstTree.TYPE_FILE:
                if min_offset is None:
                    min_offset = int.from_bytes(fstbin_data[i*12+4:i*12+8], "big")
                    continue
                min_offset = min(min_offset, int.from_bytes(fstbin_data[i*12+4:i*12+8], "big"))
        return min_offset
    def unpack(self, iso_path:Path, folder_path:Path):
        """
        Unpack takes an GCM/iso file and unpack it in a folder.
        input: iso_path = Path
        input: folder_path = Path
        """
        with iso_path.open("rb") as iso_file:
            self.__bootbin = BootBin(iso_file.read(BootBin.LEN))
            if self.__bootbin.dvd_magic() != Gcm.DVD_MAGIC:
                raise InvalidDVDMagicError("Error - Invalid DVD format - this tool is for ISO/GCM files.")

            self.__bi2bin = Bi2Bin(iso_file.read(Bi2Bin.LEN))

            iso_file.seek(Gcm.APPLOADERLEN_OFFSET)
            size = int.from_bytes(iso_file.read(4), "big")
            trailerSize = int.from_bytes(iso_file.read(4), "big")
            
            apploader_size = Gcm.APPLOADER_HEADER_LEN + size + trailerSize
            
            iso_file.seek(Gcm.APPLOADER_OFFSET)
            self.__apploaderimg = ApploaderImg(iso_file.read(apploader_size))

            fstbin_offset = self.__bootbin.fst_offset()
            fstbin_len = self.__bootbin.fst_len()
            iso_file.seek( fstbin_offset )
            fstbin_data = iso_file.read( fstbin_len )

            dol_offset = self.__bootbin.dol_offset()
            iso_file.seek( dol_offset )
            dol = Dol()
            dolheader_data = iso_file.read(Dol.HEADER_LEN)
            dol_len = dol.get_dol_len( dolheader_data )
            bootdol_data = dolheader_data + iso_file.read( dol_len - Dol.HEADER_LEN )

            if folder_path == Path("."):
                folder_path = Path(f"{self.__bootbin.game_code()}-{self.__bootbin.disc_number():02}")
            if folder_path.is_dir():
                raise InvalidUnpackFolderError(f"Error - \"{folder_path}\" already exist. Remove this folder or use another name for the unpack folder.")
            
            logging.info(f"unpacking \"{iso_path}\" in \"{folder_path}\"")
            sys_path = folder_path / "sys"
            sys_path.mkdir(parents=True)

            logging.debug(f"{iso_path}(0x0:0x{BootBin.LEN:x}) -> {sys_path / 'boot.bin'}")
            (sys_path / "boot.bin").write_bytes(self.__bootbin.data())
            logging.debug(f"{iso_path}(0x440:0x{Gcm.APPLOADER_OFFSET:x}) -> {sys_path / 'bi2.bin'}")
            (sys_path / "bi2.bin" ).write_bytes(self.__bi2bin.data())
            logging.debug(f"{iso_path}(0x{Gcm.APPLOADER_OFFSET:x}:0x{Gcm.APPLOADER_OFFSET + apploader_size:x} -> {sys_path / 'apploader.img'}")
            (sys_path / "apploader.img").write_bytes(self.__apploaderimg.data())
            logging.debug(f"{iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x}) -> {sys_path / 'fst.bin'}")
            (sys_path / "fst.bin").write_bytes(fstbin_data)
            logging.debug(f"{iso_path}(0x{dol_offset:x}:0x{dol_offset + dol_len:x}) -> {sys_path / 'boot.dol'}")
            (sys_path / "boot.dol").write_bytes(bootdol_data)

            # Generate conf from sys files
            self.__save_conf(sys_path)

            root_path = folder_path / "root"
            root_path.mkdir()
            
            # And now we parse FST data to unpack all files in the GCM iso file
            dir_id_path = {0: root_path}
            currentdir_path = root_path

            # root: id=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big")
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when id reach next dir
            nextdir_arr = [ nextdir ]

            for id in range(1, base_names // 12):
                i = id * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big")
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big"):].split(b"\x00")[0].decode("utf-8")
                
                while id == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FstTree.TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big")
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big")

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_id_path[parentdir] / name
                    dir_id_path[id] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big")
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big")

                    iso_file.seek(fileoffset)
                    (currentdir_path / name).write_bytes( iso_file.read(filesize) )

                    logging.debug(f"{iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x}) -> {currentdir_path / name}")
    def pack(self, folder_path:Path, iso_path:Path = None, disable_ignore:bool = False, skip_conf:bool = False):
        """
        Pack takes a folder unpacked by the pack command and pack it in a GCM/iso file.
        input: folder_path = Path
        input: iso_path = Path
        """
        if iso_path is None:
            iso_path = folder_path.parent / Path(folder_path.name).with_suffix(".iso")
        if iso_path.is_file():
            raise InvalidPackIsoError(f"Error - {iso_path} already exist. Remove this file or use another GCM file name.")

        try:
            with iso_path.open("wb") as iso_file:
                sys_path = folder_path / "sys"
                
                self.__bootbin = BootBin((sys_path / "boot.bin").read_bytes())
                self.__bi2bin = Bi2Bin((sys_path / "bi2.bin").read_bytes())
                self.__apploaderimg = ApploaderImg((sys_path / "apploader.img").read_bytes())

                # Patch boot.bin bi2.bin and apploader.img if system.conf is enabled
                if not skip_conf:
                    self.__load_conf(sys_path)
                if self.__bootbin.fst_len() > self.__bootbin.fst_max_len():
                    raise InvalidFSTSizeError(f"Error - fst.bin max length < fst.bin length in boot.bin offset 0x{BootBin.FSTMAXLEN_OFFSET:x}:0x{BootBin.FSTMAXLEN_OFFSET+4:x}.")

                logging.debug(f"{sys_path / 'boot.bin'}      -> {iso_path}(0x0:0x{BootBin.LEN:x})")
                iso_file.write(self.__bootbin.data())
                logging.debug(f"{sys_path / 'bi2.bin'}       -> {iso_path}(0x{BootBin.LEN:x}:0x{Gcm.APPLOADER_OFFSET:x})")
                iso_file.write(self.__bi2bin.data())

                apploader_end_offset = Gcm.APPLOADER_OFFSET + self.__apploaderimg.len()
                logging.debug(f"{sys_path / 'apploader.img'} -> {iso_path}(0x{Gcm.APPLOADER_OFFSET:x}:0x{apploader_end_offset:x}")
                iso_file.write(self.__apploaderimg.data())

                fstbin_offset = self.__bootbin.fst_offset()
                fstbin_len = self.__bootbin.fst_len()
                fstbin_end_offset = fstbin_offset + fstbin_len
                if (sys_path / "fst.bin").stat().st_size != fstbin_len:
                    raise InvalidFSTSizeError(f"Error - Invalid fst.bin length in boot.bin offset 0x{BootBin.FSTLEN_OFFSET:x}:0x{BootBin.FSTLEN_OFFSET+4:x}.")
                logging.debug(f"{sys_path / 'fst.bin'}       -> {iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x})")
                iso_file.seek( fstbin_offset )
                fstbin_data = (sys_path / "fst.bin").read_bytes()
                iso_file.write( fstbin_data )
                
                dol_offset = self.__bootbin.dol_offset()
                dol_end_offset = dol_offset + (sys_path / 'boot.dol').stat().st_size

                min_file_offset = self.__get_min_file_offset(fstbin_data)

                # FST can be before the dol or after
                # We control values to avoid Overflows
                if not disable_ignore:
                    if not Gcm.APPLOADER_OFFSET < dol_offset < dol_end_offset <= fstbin_offset and not \
                        fstbin_offset < dol_offset < dol_end_offset <= min_file_offset:
                        raise DolSizeOverflowError("Error - The dol length has been increased and overflow on next file or on FST. To solve this check the sys/system.conf file if used or use --rebuild-fst.")

                if not Gcm.APPLOADER_OFFSET < fstbin_offset < fstbin_end_offset <= dol_offset and not \
                    dol_end_offset <= fstbin_offset < fstbin_end_offset <= min_file_offset:
                    raise FstSizeOverflowError("Error - The FST length has been increased and overflow on next file or on dol. To solve this check the sys/system.conf file if used or use --rebuild-fst.")

                if Gcm.APPLOADER_OFFSET < dol_offset < apploader_end_offset or \
                    Gcm.APPLOADER_OFFSET < fstbin_offset < apploader_end_offset:
                    raise ApploaderOverflowError("Error - The apploader length has been increased and overflow on dol or on FST. To solve this check the sys/system.conf file if used or use --rebuild-fst.")

                logging.debug(f"{sys_path / 'boot.dol'}      -> {iso_path}(0x{dol_offset:x}:0x{dol_end_offset:x})")
                iso_file.seek( dol_offset )
                iso_file.write( (sys_path / "boot.dol").read_bytes() )

                # Now parse fst.bin for writing files in the iso
                dir_id_path = {0: folder_path / "root"}
                currentdir_path = folder_path / "root"

                # root: id=0 so nextdir is the end
                nextdir = int.from_bytes(fstbin_data[8:12], "big")
                # offset of filenames block
                base_names = nextdir * 12
                # go to parent when id reach next dir
                nextdir_arr = [ nextdir ]

                # Check if there is new / removed files or dirs in the root folder
                if nextdir - 1 != len(list(currentdir_path.glob("**/*"))):
                    raise InvalidRootFileFolderCountError(f"Error - Invalid file & folders count inside {currentdir_path}. Use --rebuild-fst to update the FST before packing.")

                for id in range(1, base_names // 12):
                    i = id * 12
                    file_type = int.from_bytes(fstbin_data[i:i+1], "big")
                    name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big"):].split(b"\x00")[0].decode("utf-8")
                    
                    while id == nextdir_arr[-1]:
                        currentdir_path = currentdir_path.parent
                        nextdir_arr.pop()

                    if file_type == FstTree.TYPE_DIR:
                        nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big")
                        parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big")

                        nextdir_arr.append( nextdir )
                        currentdir_path = dir_id_path[parentdir] / name
                        dir_id_path[id] = currentdir_path
                        if not currentdir_path.is_dir():
                            raise FSTDirNotFoundError(f"Error - FST dir {currentdir_path} not found in the root directory. "
                                "The dir has been removed or renamed. Use --rebuild-fst to update the FST and avoid this error."
                                "Warning: DVD SDK use dirnames to load files from the GCM/iso.")
                    else:
                        if not (currentdir_path / name).is_file():
                            raise FSTFileNotFoundError(f"Error - FST file {currentdir_path / name} not found in the root directory. "
                                "The file has been removed or renamed. Use --rebuild-fst to update the FST and avoid this error."
                                "Warning: DVD SDK use filenames to load files from the GCM/iso.")
                        
                        file_offset = int.from_bytes(fstbin_data[i+4:i+8], "big")
                        file_len   = int.from_bytes(fstbin_data[i+8:i+12], "big")

                        if (currentdir_path / name).stat().st_size != file_len:
                            raise InvalidFSTFileSizeError(f"Error - Invalid file length: {currentdir_path / name} - use --rebuild-fst before packing files in the iso.")
                        logging.debug(f"{currentdir_path / name} -> {iso_path}(0x{file_offset:x}:0x{file_offset + file_len:x})")
                        iso_file.seek(file_offset)
                        iso_file.write( (currentdir_path / name).read_bytes() )
        except (InvalidFSTSizeError, DolSizeOverflowError, InvalidRootFileFolderCountError, InvalidFSTFileSizeError, \
            FSTDirNotFoundError, FSTFileNotFoundError, InvalidConfValueError, FstSizeOverflowError, ApploaderOverflowError):
            iso_path.unlink()
            raise
    def rebuild_fst(self, folder_path:Path, align:int, skip_conf:bool):
        """
        Rebuild FST generate a new file system by using all files in the root folder
        it patch boot.bin caracteristics, apploader.img and also file system changes.
        Game dol use FST filenames to find files so be carrefull when changing the 
        root filesystem. Align is 0x8000 for APDCM.
        input: folder_path = Path
        input: align = int
        """
        root_path = folder_path / "root"
        sys_path = folder_path / "sys"

        self.__bootbin = BootBin((sys_path / "boot.bin").read_bytes())
        self.__bi2bin = Bi2Bin((sys_path / "bi2.bin").read_bytes())
        self.__apploaderimg = ApploaderImg((sys_path / "apploader.img").read_bytes())

        (
            dol_offset,
            fst_offset,
            fst_len,
            fst_max_len,
            user_position,
            user_length
        ) = self.__load_conf(sys_path, get_conf_values = True) if not skip_conf else (None, None, 0, None, None, None)

        if dol_offset is None:
            dol_offset = align_top(Gcm.APPLOADER_OFFSET + (sys_path / "apploader.img").stat().st_size, align)
            logging.info(f"Patching sys/boot.bin offset 0x{BootBin.DOLOFFSET_OFFSET:x} with new dol offset (0x{dol_offset:x}).")
            self.__bootbin.set_dol_offset(dol_offset)

        dol_end_offset = align_top(dol_offset + (sys_path / "boot.dol").stat().st_size, align)
        # Default = FST after dol
        if fst_offset is None:
            fst_offset = dol_end_offset
            logging.info(f"Patching sys/boot.bin offset 0x{BootBin.FSTOFFSET_OFFSET:x} with new FST offset (0x{fst_offset:x}).")
            self.__bootbin.set_fst_offset(fst_offset)
        
        fst_end_offset = fst_offset + fst_len
        fst_tree = FstTree(root_path, max(dol_end_offset, fst_offset, fst_end_offset), \
            is_fst_last = (dol_end_offset <= fst_offset and fst_len == 0), align=align)

        # Sorting paths approach original fst sort, but in original fst specials chars are after and not before chars.
        # Files / Folders are sometimes put in arbitrary order.
        path_list = sorted([path for path in root_path.glob('**/*')], key=lambda s:Path(str(s).upper()))
        for path in path_list:
            fst_tree.add_node_by_path(path)
        logging.debug(fst_tree)

        fst_path = sys_path / "fst.bin"

        logging.info(f"Writing fst in sys/fst.bin")
        fst_path.write_bytes( fst_tree.generate_fst() )

        if fst_len == 0:
            fst_len = fst_path.stat().st_size
            logging.info(f"Patching sys/boot.bin offset 0x{BootBin.FSTLEN_OFFSET:x} with new FST size (0x{fst_len:x}).")
            self.__bootbin.set_fst_len(fst_len)

        if fst_max_len is None and fst_len > self.__bootbin.fst_max_len():
            logging.info(f"Patching sys/boot.bin offset 0x{BootBin.FSTMAXLEN_OFFSET:x} with new FST max size (0x{fst_len:x}).")
            self.__bootbin.set_fst_max_len(fst_len)

        if user_position is None:
            # Allow fixed fst_len or dol after FST fixed by conf
            user_position = max(fst_tree.user_position(), fst_offset + fst_len, dol_end_offset)
            logging.info(f"Patching sys/boot.bin offset 0x434 with new user position (0x{user_position:x}).")
            self.__bootbin.set_user_position(user_position)
        
        if user_length is None:
            user_length = fst_tree.user_length()
            logging.info(f"Patching sys/boot.bin offset 0x438 with new user length (0x{user_length:x}).")
            self.__bootbin.set_user_length(user_length)

        (sys_path / "boot.bin").write_bytes(self.__bootbin.data())
    def __get_sys_from_folder(self, folder_path:Path):
        """
        Load system files from an unpacked GCM/iso folder and returns informations for the stats command.
        input: folder_path = Path
        return (dol_len:int, fstbin_data:bytes)
        load __bootbin, __bi2bin, __apploaderimg
        """
        sys_path = folder_path / "sys"
        self.__bootbin = BootBin((sys_path / "boot.bin").read_bytes())
        self.__bi2bin = Bi2Bin((sys_path / "bi2.bin").read_bytes())
        self.__apploaderimg = ApploaderImg((sys_path / "apploader.img").read_bytes())

        dol_len = (sys_path / "boot.dol").stat().st_size
        fstbin_data = (sys_path / "fst.bin").read_bytes()
        return (dol_len, fstbin_data)
    def __get_sys_from_file(self, file_path:Path):
        """
        Load system files from a GCM/iso file and returns informations for the stats command.
        input: folder_path = Path
        return (dol_len:int, fstbin_data:bytes)
        load __bootbin, __bi2bin, __apploaderimg
        """
        dol_len = None
        fstbin_data = None
        with file_path.open("rb") as iso_file:
            self.__bootbin = BootBin(iso_file.read(BootBin.LEN))
            self.__bi2bin = Bi2Bin(iso_file.read(Bi2Bin.LEN))
            
            iso_file.seek(Gcm.APPLOADERLEN_OFFSET)
            apploader_size = Gcm.APPLOADER_HEADER_LEN + int.from_bytes(iso_file.read(4), "big") + int.from_bytes(iso_file.read(4), "big")
            iso_file.seek(Gcm.APPLOADER_OFFSET)
            self.__apploaderimg = ApploaderImg(iso_file.read(apploader_size))

            dol = Dol()
            iso_file.seek( self.__bootbin.dol_offset() )
            dol_len = dol.get_dol_len( iso_file.read(Dol.HEADER_LEN) )
            iso_file.seek( self.__bootbin.fst_offset() )
            fstbin_data = iso_file.read(self.__bootbin.fst_len())
        return (dol_len, fstbin_data)
    def stats(self, path:Path, align:int = 4):
        """
        Print SYS files informations, global memory mapping, empty spaces inside the GCM/iso
        input:
        * path = Path (folder or iso/GCM file)
        * align = int
        """
        (dol_len, fstbin_data) = self.__get_sys_from_folder(path) if path.is_dir() else self.__get_sys_from_file(path)

        global_stats = f"# Stats for \"{path}\":\n\n" + \
            "[boot.bin]\n" + \
            f"GameCode = {self.__bootbin.game_code()}\n" + \
            f"MakerCode = {self.__bootbin.maker_code()}\n" + \
            f"DiscNumber = {self.__bootbin.disc_number()}\n" + \
            f"GameVersion = {self.__bootbin.game_version()}\n" + \
            f"AudioStreaming = {self.__bootbin.audio_streaming()}\n" + \
            f"StreamBufferSize = {self.__bootbin.stream_buffer_size()}\n" + \
            f"DVDMagic = 0x{self.__bootbin.dvd_magic().hex()}\n" + \
            f"GameName = {self.__bootbin.game_name()}\n" + \
            f"DolOffset = 0x{self.__bootbin.dol_offset():x}\n" + \
            f"FstOffset = 0x{self.__bootbin.fst_offset():x}\n" + \
            f"FstLen = 0x{self.__bootbin.fst_len():x}\n" + \
            f"FstMaxLen = 0x{self.__bootbin.fst_max_len():x}\n" + \
            f"UserPosition = 0x{self.__bootbin.user_position():x}\n" + \
            f"UserLength = 0x{self.__bootbin.user_length():x}\n\n" + \
            "[bi2.bin]\n" + \
            f"DebugMonitorSize = 0x{self.__bi2bin.debug_monitor_size():x}\n" + \
            f"SimulatedMemorySize = 0x{self.__bi2bin.simulated_memory_size():x}\n" + \
            f"ArgumentOffset = 0x{self.__bi2bin.argument_offset():x}\n" + \
            f"DebugFlag = {self.__bi2bin.debug_flag()}\n" + \
            f"TrackLocation = 0x{self.__bi2bin.track_location():x}\n" + \
            f"TrackSize = 0x{self.__bi2bin.track_size():x}\n" + \
            f"CountryCode = {self.__bi2bin.country_code()}\n" + \
            f"TotalDisc = {self.__bi2bin.total_disc()}\n" + \
            f"LongFileNameSupport = {self.__bi2bin.long_file_name_support()}\n" + \
            f"DolLimit = 0x{self.__bi2bin.dol_limit():x}\n\n" + \
            "[apploader.img]\n" + \
            f"Version = {self.__apploaderimg.version()}\n" + \
            f"EntryPoint = 0x{self.__apploaderimg.entry_point():x}\n" + \
            f"Size = 0x{self.__apploaderimg.size():x}\n" + \
            f"TrailerSize = 0x{self.__apploaderimg.trailer_size():x}\n"

        print(global_stats)

        class MemoryObject:
            def __init__(self, name:str, beg_offset:int, length:int):
                self.name = name
                self.beg_offset = beg_offset
                self.length = length
                self.end_offset = beg_offset + length
            def __str__(self):
                return f"| {self.beg_offset:08x} | {self.end_offset:08x} | {self.length:08x} | {self.name}"

        mem_obj_list = [
            MemoryObject("boot.bin", 0, BootBin.LEN),
            MemoryObject("bi2.bin", 0x440, Bi2Bin.LEN),
            MemoryObject("apploader.img", Gcm.APPLOADER_OFFSET, self.__apploaderimg.len()),
            MemoryObject("fst.bin", self.__bootbin.fst_offset(), self.__bootbin.fst_len()),
            MemoryObject("boot.dol", self.__bootbin.dol_offset(), dol_len)]

        dir_id_path = {0: Path(".")}
        currentdir_path = Path(".")

        # root: id=0 so nextdir is the end
        nextdir = int.from_bytes(fstbin_data[8:12], "big")
        # offset of filenames block
        base_names = nextdir * 12
        # go to parent when id reach next dir
        nextdir_arr = [ nextdir ]

        for id in range(1, base_names // 12):
            i = id * 12
            file_type = int.from_bytes(fstbin_data[i:i+1], "big")
            name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big"):].split(b"\x00")[0].decode("utf-8")
            
            while id == nextdir_arr[-1]:
                currentdir_path = currentdir_path.parent
                nextdir_arr.pop()

            if file_type == FstTree.TYPE_DIR:
                nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big")
                parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big")

                nextdir_arr.append( nextdir )
                currentdir_path = dir_id_path[parentdir] / name
                dir_id_path[id] = currentdir_path
            else:
                fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big")
                filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big")
                mem_obj_list.append( MemoryObject(str(currentdir_path / name), fileoffset, filesize) )

        mem_obj_list.sort(key=lambda x: x.beg_offset)

        empty_space_list = []
        collision_list = []
        last_mem_obj = mem_obj_list[2]
        for mem_obj in mem_obj_list[3:]:
            last_aligned = align_top(last_mem_obj.end_offset, align)
            if last_aligned < mem_obj.beg_offset:
                empty_space_list.append( MemoryObject("", last_aligned, mem_obj.beg_offset - last_aligned) )
            elif last_aligned > mem_obj.beg_offset:
                collision_list += [last_mem_obj, mem_obj]
            last_mem_obj = mem_obj
        
        self.__print("Global memory mapping:", mem_obj_list)
        if empty_space_list:
            self.__print(f"Empty spaces (align={align}):", empty_space_list)
        if collision_list:
            self.__print(f"Collisions (align={align}):", collision_list)
    def __print(self, title:str, mem_obj_list):
        """
        Print a table with a title.
        * input: title = str
        * input: mem_obj_list = [MemoryObject, ...]
        """
        full_title = "#"*70+f"\n# {title}\n"+"#"*70+"\n| b offset | e offset | length   | Name\n|"+"-"*69+"\n"
        print(full_title + "\n".join([str(mem_obj) for mem_obj in mem_obj_list]))


def pack(p_input:Path, p_output:Path, disable_ignore:bool, skip_conf:bool = False):
    logging.info("### Pack in new GCM iso")
    if(p_output == Path(".")):
        p_output = Path(p_input.with_suffix(".iso"))
    logging.info(f"Packing folder \"{p_input}\" in \"{p_output}\"")
    gcm.pack(p_input, p_output, disable_ignore, skip_conf)


def unpack(p_input:Path, p_output:Path):
    logging.info("### Unpack GCM iso in new folder")
    gcm.unpack(p_input, p_output)


def rebuild_fst(p_input:Path, align:int, skip_conf:bool = False):
    logging.info("### Rebuilding FST and patching boot.bin")
    if args.align < 1:
        raise BadAlignError("Error - Align must be > 0.")
    logging.info(f"Using alignment: {args.align}")
    gcm.rebuild_fst(p_input, align, skip_conf)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='ISO/GCM packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-a', '--align', type=int, help='-a=10: alignment of files in the GCM ISO (default value is 4)', default=4)
    parser.add_argument('-di', '--disable-ignore', action='store_true', help='-di: disable dol collisions verification when packing files sharing the same place in the GCM.')
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack', action='store_true', help="-p source_folder (dest_file.iso): Pack source_folder in new file source_folder.iso or dest_file.iso if specified.")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_iso.iso (dest_folder): Unpack the GCM/ISO in new folder source_iso or dest_folder if specified.")
    group.add_argument('-s', '--stats', action='store_true', help="-s source_iso.iso or source_folder (-a 4): Get stats about GCM, FST, memory, lengths and offsets.")
    group.add_argument('-r', '--rebuild-fst', action='store_true', help="-r game_folder (-a 4): Rebuild the game_folder/sys/fst.bin using files in game_folder/root. For ADPCM (...) use 0x8000 align.")
    group.add_argument('-ur', '--unpack-rebuild-fst', action='store_true', help="-ur source_iso.iso (dest_folder) (-a 4): Unpack and rebuild the FST.")
    group.add_argument('-rp', '--rebuild-fst-pack', action='store_true', help="-rp source_folder (dest_file.iso) (-a 4): Rebuild the FST and pack.")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    gcm = Gcm()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        pack(p_input, p_output, args.disable_ignore)
    elif args.unpack:
        unpack(p_input, p_output)
    elif args.stats:
        gcm.stats(p_input)
    elif args.rebuild_fst:
        rebuild_fst(p_input, args.align)
    elif args.rebuild_fst_pack:
        rebuild_fst(p_input, args.align) # rebuild fst parse and patch with conf
        pack(p_input, p_output, args.disable_ignore, skip_conf = True)
    elif args.unpack_rebuild_fst:
        unpack(p_input, p_output) # conf isn't enabled yet
        rebuild_fst(p_output, args.align, skip_conf = True)
