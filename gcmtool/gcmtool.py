#!/usr/bin/env python3
from pathlib import Path
import logging


__version__ = "0.1.2"
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
# raised during pack when FST folder entry has an invalid nextdir id value; this happen when file and folder has been added/removed
class InvalidRootFileFolderCountError(Exception): pass
# raised during pack when FST file entry has a different value than the file being packed; this happen when a file has been edited changing it's size
class InvalidFSTFileSizeError(Exception): pass
# raised during pack when FST dir name is not found in the root folder; this happen when a dir is renamed or removed
class FSTDirNotFoundError(Exception): pass
# raised during pack when FST file name is not found in the root folder; this happen when a file is renamed or removed
class FSTFileNotFoundError(Exception): pass
# raised during the stats command when align make file offsets collisions (this happen when given align > real files align); or when using an invalid align
class BadAlignError(Exception): pass


def align_offset(offset:int, align:int):
    """
    Give the upper rounded offset aligned using the align value.
    input: offset = int
    input: align = int
    return offset = int
    """
    if offset % align != 0:
        offset += align - (offset % align)
    return offset


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
    def __init__(self, root_path:Path, fst_offset:int, align:int = 4):
        # as said before we don't want to add parents folder that don't are used in the folder we are packing.
        self.__root_path_length = len(root_path.parts)
        self.__root_node = Folder(root_path.name, None)
        self.__align = align
        self.__name_block = b""
        self.__fst_block = b""
        self.__nameblock_length = 0
        self.__current_file_offset = fst_offset
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
        return align_offset(self.__count_childs(self.__root_node)*12 + 12 + self.__nameblock_length, self.__align)
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
            self.__current_file_offset = align_offset(self.__current_file_offset + node.size(), self.__align)
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
        informations:
        * name
        * size
        * parent id & parent->child
        input:
        * path = Path (folder / file)
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
        knowing where we can begin to add files
        """
        self.__current_file_offset += self.__get_fst_length()
        self.__prepare()
        return self.__fst_block + self.__name_block


class BootBin:
    """
    BootBin group all operations related to the boot.bin system file
    using this class avoid errors and it's easier to use it elsewhere
    this groupment add meaning to hex values but we can also patch it.
    Constructor:
    * datas = bytes or bytearray if edit is needed of the boot.bin
    """
    LEN = 0x440
    DOLOFFSET_OFFSET = 0x420
    FSTOFFSET_OFFSET = 0x424
    FSTLEN_OFFSET = 0x428
    MAXFSTLEN_OFFSET = 0x42c
    __data = None
    def __init__(self, data:bytes):
        self.__data = bytearray(data)
    def data(self): return self.__data
    def dvd_magic(self):
        return self.__data[0x1c:0x20]
    def fstbin_offset(self):
        return int.from_bytes(self.__data[BootBin.FSTOFFSET_OFFSET:BootBin.FSTOFFSET_OFFSET+4],"big", signed=False)
    def fstbin_len(self):
        return int.from_bytes(self.__data[BootBin.FSTLEN_OFFSET:BootBin.FSTLEN_OFFSET+4],"big", signed=False)
    def dol_offset(self):
        return int.from_bytes(self.__data[BootBin.DOLOFFSET_OFFSET:BootBin.DOLOFFSET_OFFSET+4],"big", signed=False)
    def game_code(self):
        return self.__data[:4].decode('utf-8')
    def disc_number(self):
        return int.from_bytes(self.__data[6:7], 'big', signed=False)
    def set_dol_offset(self, offset:int):
        self.__data[BootBin.DOLOFFSET_OFFSET:BootBin.DOLOFFSET_OFFSET+4] = offset.to_bytes(4, "big")
    def set_fst_offset(self, offset:int):
        self.__data[BootBin.FSTOFFSET_OFFSET:BootBin.FSTOFFSET_OFFSET+4] = offset.to_bytes(4, "big")
    def set_fst_len(self, size:int):
        self.__data[BootBin.FSTLEN_OFFSET:BootBin.FSTLEN_OFFSET+4] = size.to_bytes(4, "big")
    def set_max_fst_len(self, size:int):
        self.__data[BootBin.MAXFSTLEN_OFFSET:BootBin.MAXFSTLEN_OFFSET+4] = size.to_bytes(4, "big")


class Dol:
    """
    Dol is used to find the dol size and group data adding meaning to hex values and allowing to get it's size.
    """
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
            dol_len += int.from_bytes(dolheader_data[Dol.HEADER_SECTIONLENTABLE_OFFSET+i*4:Dol.HEADER_SECTIONLENTABLE_OFFSET+(i+1)*4], "big", signed=False)
        return dol_len


class Gcm:
    """
    Gcm handle all operations needed by the command parser.
    File format informations: https://sudonull.com/post/68549-Gamecube-file-system-device
    """
    BI2BIN_LEN = 0x2000
    APPLOADER_HEADER_LEN = 0x20
    APPLOADER_OFFSET = 0x2440
    APPLOADERSIZE_OFFSET = 0x2454
    DVD_MAGIC = b"\xC2\x33\x9F\x3D"
    def __get_min_file_offset(self, fstbin_data:bytes):
        "Get the min file offset to check if there is an overflow."
        min_offset = None
        for i in range(2, int.from_bytes(fstbin_data[8:12], "big", signed=False)):
            if int.from_bytes(fstbin_data[i*12:i*12+1], "big", signed=False) == FstTree.TYPE_FILE:
                if min_offset is None:
                    min_offset = int.from_bytes(fstbin_data[i*12+4:i*12+8], "big", signed=False)
                    continue
                min_offset = min(min_offset, int.from_bytes(fstbin_data[i*12+4:i*12+8], "big", signed=False))
        return min_offset
    def unpack(self, iso_path:Path, folder_path:Path):
        """
        unpack takes an GCM/iso and unpack it in a folder.
        input: iso_path = Path
        input: folder_path = Path
        """
        with iso_path.open("rb") as iso_file:
            bootbin = BootBin(iso_file.read(BootBin.LEN))
            if bootbin.dvd_magic() != Gcm.DVD_MAGIC:
                raise InvalidDVDMagicError("Error - Invalid DVD format - this tool is for ISO/GCM files")

            bi2bin_data = iso_file.read(Gcm.BI2BIN_LEN)

            iso_file.seek(Gcm.APPLOADERSIZE_OFFSET)
            size = int.from_bytes(iso_file.read(4), "big", signed=False)
            trailerSize = int.from_bytes(iso_file.read(4), "big", signed=False)
            
            apploader_size = Gcm.APPLOADER_HEADER_LEN + size + trailerSize
            
            iso_file.seek(Gcm.APPLOADER_OFFSET)
            apploaderimg_data = iso_file.read(apploader_size)

            fstbin_offset = bootbin.fstbin_offset()
            fstbin_len = bootbin.fstbin_len()
            iso_file.seek( fstbin_offset )
            fstbin_data = iso_file.read( fstbin_len )

            dol_offset = bootbin.dol_offset()
            iso_file.seek( dol_offset )
            dol = Dol()
            dolheader_data = iso_file.read(Dol.HEADER_LEN)
            dol_len = dol.get_dol_len( dolheader_data )
            bootdol_data = dolheader_data + iso_file.read( dol_len - Dol.HEADER_LEN )

            if folder_path == Path("."):
                folder_path = Path(f"{bootbin.game_code()}-{bootbin.disc_number():02}")
            if folder_path.is_dir():
                raise InvalidUnpackFolderError(f"Error - \"{folder_path}\" already exist. Remove this folder or use another name for the unpack folder.")
            
            logging.info(f"unpacking \"{iso_path}\" in \"{folder_path}\"")
            sys_path = folder_path / "sys"
            sys_path.mkdir(parents=True)

            logging.debug(f"{iso_path}(0x0:0x{BootBin.LEN:x}) -> {sys_path / 'boot.bin'}")
            (sys_path / "boot.bin").write_bytes(bootbin.data())
            logging.debug(f"{iso_path}(0x440:0x{Gcm.APPLOADER_OFFSET:x}) -> {sys_path / 'bi2.bin'}")
            (sys_path / "bi2.bin" ).write_bytes(bi2bin_data)
            logging.debug(f"{iso_path}(0x{Gcm.APPLOADER_OFFSET:x}:0x{Gcm.APPLOADER_OFFSET + apploader_size:x} -> {sys_path / 'apploader.img'}")
            (sys_path / "apploader.img").write_bytes(apploaderimg_data)
            logging.debug(f"{iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x}) -> {sys_path / 'fst.bin'}")
            (sys_path / "fst.bin").write_bytes(fstbin_data)
            logging.debug(f"{iso_path}(0x{dol_offset:x}:0x{dol_offset + dol_len:x}) -> {sys_path / 'boot.dol'}")
            (sys_path / "boot.dol").write_bytes(bootdol_data)

            root_path = folder_path / "root"
            root_path.mkdir()
            
            # And now we parse FST data to unpack all files in the GCM iso file
            dir_id_path = {0: root_path}
            currentdir_path = root_path

            # root: id=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when id reach next dir
            nextdir_arr = [ nextdir ]

            for id in range(1, base_names // 12):
                i = id * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                
                while id == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FstTree.TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_id_path[parentdir] / name
                    dir_id_path[id] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    iso_file.seek(fileoffset)
                    (currentdir_path / name).write_bytes( iso_file.read(filesize) )

                    logging.debug(f"{iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x}) -> {currentdir_path / name}")
    def pack(self, folder_path:Path, iso_path:Path = None):
        """
        pack takes a folder unpacked by the pack command and pack it in a GCM/iso file.
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
                
                logging.debug(f"{sys_path / 'boot.bin'}      -> {iso_path}(0x0:0x{BootBin.LEN:x})")
                bootbin = BootBin((sys_path / "boot.bin").read_bytes())
                iso_file.write(bootbin.data())
                logging.debug(f"{sys_path / 'bi2.bin'}       -> {iso_path}(0x{BootBin.LEN:x}:0x{Gcm.APPLOADER_OFFSET:x})")
                iso_file.write((sys_path / "bi2.bin").read_bytes())
                logging.debug(f"{sys_path / 'apploader.img'} -> {iso_path}(0x{Gcm.APPLOADER_OFFSET:x}:0x{Gcm.APPLOADER_OFFSET + (sys_path / 'apploader.img').stat().st_size:x}")
                iso_file.write((sys_path / "apploader.img").read_bytes())

                fstbin_offset = bootbin.fstbin_offset()
                fstbin_len = bootbin.fstbin_len()
                if (sys_path / "fst.bin").stat().st_size != fstbin_len:
                    raise InvalidFSTSizeError(f"Error - Invalid fst.bin size in boot.bin offset 0x{BootBin.FSTLEN_OFFSET:x}:0x{BootBin.FSTLEN_OFFSET+4:x}!")
                logging.debug(f"{sys_path / 'fst.bin'}       -> {iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x})")
                iso_file.seek( fstbin_offset )
                fstbin_data = (sys_path / "fst.bin").read_bytes()
                iso_file.write( fstbin_data )
                
                dol_offset = bootbin.dol_offset()
                dol_end_offset = dol_offset + (sys_path / 'boot.dol').stat().st_size
                # FST can be before the dol or after
                if dol_offset < fstbin_offset < dol_end_offset or (fstbin_offset < dol_offset and dol_end_offset > self.__get_min_file_offset(fstbin_data)):
                    raise DolSizeOverflowError("Error - The dol size has been increased and overflow on next file or on FST. To solve this use --rebuild-fst.")
                logging.debug(f"{sys_path / 'boot.dol'}      -> {iso_path}(0x{dol_offset:x}:0x{dol_end_offset:x})")
                iso_file.seek( dol_offset )
                iso_file.write( (sys_path / "boot.dol").read_bytes() )

                # Now parse fst.bin for writing files in the iso
                dir_id_path = {0: folder_path / "root"}
                currentdir_path = folder_path / "root"

                # root: id=0 so nextdir is the end
                nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
                # offset of filenames block
                base_names = nextdir * 12
                # go to parent when id reach next dir
                nextdir_arr = [ nextdir ]

                # Check if there is new / removed files or dirs in the root folder
                if nextdir - 1 != len(list(currentdir_path.glob("**/*"))):
                    raise InvalidRootFileFolderCountError(f"Error - Invalid file & folders count inside {currentdir_path}. Use --rebuild-fst to update the FST before packing.")

                for id in range(1, base_names // 12):
                    i = id * 12
                    file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                    name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                    
                    while id == nextdir_arr[-1]:
                        currentdir_path = currentdir_path.parent
                        nextdir_arr.pop()

                    if file_type == FstTree.TYPE_DIR:
                        nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                        parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

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
                        
                        file_offset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                        file_len   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                        if (currentdir_path / name).stat().st_size != file_len:
                            raise InvalidFSTFileSizeError(f"Error - Invalid file size: {currentdir_path / name} - use --rebuild-fst before packing files in the iso.")
                        logging.debug(f"{currentdir_path / name} -> {iso_path}(0x{file_offset:x}:0x{file_offset + file_len:x})")
                        iso_file.seek(file_offset)
                        iso_file.write( (currentdir_path / name).read_bytes() )
        except (InvalidFSTSizeError, DolSizeOverflowError, InvalidRootFileFolderCountError, InvalidFSTFileSizeError, FSTDirNotFoundError, FSTFileNotFoundError):
            iso_path.unlink()
            raise
    def rebuild_fst(self, folder_path:Path, align:int):
        """
        Rebuild FST generate a new file system by using all files in the root folder
        it also patch boot.bin caracteristics and apploader.img or also file system changes.
        Game dol use filenames to find files so be carrefull when changing the root filesystem.
        input: folder_path = Path
        input: align = int
        """
        root_path = folder_path / "root"
        sys_path = folder_path / "sys"

        dol_offset = align_offset(Gcm.APPLOADER_OFFSET + (sys_path / "apploader.img").stat().st_size, align)
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.DOLOFFSET_OFFSET:x} with new dol offset (0x{dol_offset:x})")
        bootbin = BootBin((sys_path / "boot.bin").read_bytes())
        bootbin.set_dol_offset(dol_offset)
        
        fst_offset = align_offset(dol_offset + (sys_path / "boot.dol").stat().st_size, align)
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.FSTOFFSET_OFFSET:x} with new FST offset (0x{fst_offset:x})")
        bootbin.set_fst_offset(fst_offset)
        
        fst_tree = FstTree(root_path, fst_offset, align=align)

        # Sorting paths approach original fst sort, but in original fst specials chars are after and not before chars
        path_list = sorted([path for path in root_path.glob('**/*')], key=lambda s:Path(str(s).upper()))
        for path in path_list:
            fst_tree.add_node_by_path(path)
        logging.debug(fst_tree)

        fst_path = sys_path / "fst.bin"

        logging.info(f"Writing fst in {Path('sys/fst.bin')}")
        fst_path.write_bytes( fst_tree.generate_fst() )

        fst_size = fst_path.stat().st_size
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.FSTLEN_OFFSET:x} with new FST size (0x{fst_size:x})")
        bootbin.set_fst_len(fst_size)
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.MAXFSTLEN_OFFSET:x} with new FST max size (0x{fst_size:x})")
        bootbin.set_max_fst_len(fst_size)

        (sys_path / "boot.bin").write_bytes(bootbin.data())
    def __get_sys_from_folder(self, folder_path:Path):
        """
        Load system files from an unpacked GCM/iso folder and returns informations for the stats command.
        input: folder_path = Path
        return (BootBin, apploader_size:int, dol_len:int, fstbin_data:bytes)
        """
        sys_path = folder_path / "sys"
        bootbin = BootBin((sys_path / "boot.bin").read_bytes())
        apploader_size = (sys_path / "apploader.img").stat().st_size
        dol_len = (sys_path / "boot.dol").stat().st_size
        fstbin_data = (sys_path / "fst.bin").read_bytes()
        return (bootbin, apploader_size, dol_len, fstbin_data)
    def __get_sys_from_file(self, file_path:Path):
        """
        Load system files from a GCM/iso file and returns informations for the stats command.
        input: folder_path = Path
        return (BootBin, apploader_size:int, dol_len:int, fstbin_data:bytes)
        """
        bootbin = None
        apploader_size = None
        dol_len = None
        fstbin_data = None
        with file_path.open("rb") as iso_file:
            bootbin = BootBin(iso_file.read(BootBin.LEN))
            iso_file.seek(Gcm.APPLOADERSIZE_OFFSET)
            apploader_size = Gcm.APPLOADER_HEADER_LEN + int.from_bytes(iso_file.read(4), "big", signed=False) + int.from_bytes(iso_file.read(4), "big", signed=False)

            dol = Dol()
            iso_file.seek( bootbin.dol_offset() )
            dol_len = dol.get_dol_len( iso_file.read(Dol.HEADER_LEN) )
            iso_file.seek( bootbin.fstbin_offset() )
            fstbin_data = iso_file.read(bootbin.fstbin_len())
        return (bootbin, apploader_size, dol_len, fstbin_data)
    def stats(self, path:Path, align:int = 4):
        """
        Print SYS files informations, global memory mapping, empty spaces inside the GCM/iso
        input:
        * path = Path (folder or iso/GCM file)
        * align = int
        """
        (bootbin, apploader_size, dol_len, fstbin_data) = self.__get_sys_from_folder(path) if path.is_dir() else self.__get_sys_from_file(path)

        # Begin offset - end offset - length - name
        mapping_lists = [
            [0, BootBin.LEN, f"{BootBin.LEN:08x}", "boot.bin"],
            [0x440, Gcm.APPLOADER_OFFSET, f"{Gcm.BI2BIN_LEN:08x}", "bi2.bin"],
            [Gcm.APPLOADER_OFFSET, Gcm.APPLOADER_OFFSET + apploader_size, f"{apploader_size:08x}", "apploader.img"],
            [bootbin.fstbin_offset(), bootbin.fstbin_offset() + bootbin.fstbin_len(), f"{bootbin.fstbin_len():08x}", "fst.bin"],
            [bootbin.dol_offset(), bootbin.dol_offset() + dol_len, f"{dol_len:08x}", "boot.dol"]]

        dir_id_path = {0: Path(".")}
        currentdir_path = Path(".")

        # root: id=0 so nextdir is the end
        nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
        # offset of filenames block
        base_names = nextdir * 12
        # go to parent when id reach next dir
        nextdir_arr = [ nextdir ]

        for id in range(1, base_names // 12):
            i = id * 12
            file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
            name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
            
            while id == nextdir_arr[-1]:
                currentdir_path = currentdir_path.parent
                nextdir_arr.pop()

            if file_type == FstTree.TYPE_DIR:
                nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                nextdir_arr.append( nextdir )
                currentdir_path = dir_id_path[parentdir] / name
                dir_id_path[id] = currentdir_path
            else:
                fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                mapping_lists.append( [fileoffset, fileoffset + filesize, f"{filesize:08x}", str(currentdir_path / name)] )

        mapping_lists.sort(key=lambda x: x[0])

        empty_space_tuples = []
        last_offset = 0
        for i in range(len(mapping_lists)):
            if last_offset < mapping_lists[i][0]:
                empty_space_tuples.append( (f"{last_offset:08x}", f"{mapping_lists[i][0]:08x}", f"{mapping_lists[i][0] - last_offset:08x}", "") )
            elif last_offset > mapping_lists[i][0]:
                raise BadAlignError(f"Error - Bad align ({align})! Offsets collision.")
            last_offset = align_offset(mapping_lists[i][1], align)
            mapping_lists[i][0] = f"{mapping_lists[i][0]:08x}"
            mapping_lists[i][1] = f"{mapping_lists[i][1]:08x}"

        print(f"# Stats for \"{path}\":")
        self.__print("Global memory mapping:", mapping_lists)
        self.__print(f"Empty spaces (align={align}):", empty_space_tuples)
    def __print(self, title:str, lines_tuples):
        """
        Print a table with a title.
        * input: title = str
        * input: lines_tuples = [(b_offset:str, e_offset:str, length:str, Name:str), ...]
        """
        stats_buffer = "#"*70+f"\n# {title}\n"+"#"*70+"\n| b offset | e offset | length   | Name\n|"+"-"*69+"\n"
        for line in lines_tuples:
            stats_buffer += "| "+" | ".join(line)+"\n"
        print(stats_buffer, end='')


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='ISO/GCM packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-a', '--align', type=int, help='-a=10: alignment of files in the GCM ISO (default value is 4)', default=4)
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack', action='store_true', help="-p source_folder (dest_file.iso): Pack source_folder in new file source_folder.iso or dest_file.iso if specified")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_iso.iso (dest_folder): Unpack the GCM/ISO in new folder source_iso or dest_folder if specified")
    group.add_argument('-s', '--stats', action='store_true', help="-s source_iso.iso or source_folder: Get stats about GCM, FST, memory, lengths and offsets.")
    group.add_argument('-r', '--rebuild-fst', action='store_true', help="-r game_folder: Rebuild the game_folder/sys/fst.bin using files in game_folder/root")
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
        logging.info("### Pack in new GCM iso")
        if(p_output == Path(".")):
            p_output = Path(p_input.with_suffix(".iso"))
        logging.info(f"packing folder \"{p_input}\" in \"{p_output}\"")
        gcm.pack(p_input, p_output)
    elif args.unpack:
        logging.info("### Unpack GCM iso in new folder")
        gcm.unpack(p_input, p_output)
    elif args.stats:
        gcm.stats(p_input)
    elif args.rebuild_fst:
        logging.info("### Rebuilding FST and patching boot.bin")
        if args.align < 1:
            raise BadAlignError("Error - Align must be > 0.")
        logging.info(f"Using alignment: {args.align}")
        gcm.rebuild_fst(p_input, args.align)
