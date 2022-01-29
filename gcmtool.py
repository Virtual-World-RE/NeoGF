#!/usr/bin/env python3
from pathlib import Path
import logging


__version__ = "0.0.10"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


def align_offset(offset:int, align:int):
    if offset % align != 0:
        offset += align - (offset % align)
    return offset


class Fst:
    TYPE_FILE = 0
    TYPE_DIR = 1


class Node:
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
    # Search child by name an return existing if found or new if not existing
    def add_child(self, node:Node):
        for child in self.__childs:
            if node.name() == child.name():
                return child
        self.__childs.append(node)
        return node
    def format(self):
        return self.type().to_bytes(1, "big") + self.name_offset().to_bytes(3, "big") + self.parent().id().to_bytes(4, "big") + self.next_dir().to_bytes(4, "big")


class FstTree(Fst):
    __root_path_length = None
    __root_node = None
    __current_id = 0
    __current_file_offset = None
    __align = None
    __fst_block = None
    __name_block = None
    __nameblock_length = None # Used to find min file_offset when fst is at the end of the iso beginning
    def __init__(self, root_path:Path, fst_offset:int, align:int = 4):
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
        result = (depth * "    ") + str(node) +"\n"
        if node.type() == FstTree.TYPE_DIR:
            for child in node.childs():
                result += self.__to_str(child, depth+1)
        return result
    # Needed to know where we can begin to write files
    def __get_fst_length(self):
        self.__generate_nameblock_length()
        return align_offset(self.__count_childs(self.__root_node)*12 + 12 + self.__nameblock_length, self.__align)
    def __generate_nameblock_length(self, node:Node = None):
        if node == None:
            node = self.__root_node
        else:
            self.__nameblock_length += len(node.name()) + 1
        if node.type() == FstTree.TYPE_DIR:
            for child in node.childs():
                self.__generate_nameblock_length(child)
    def __prepare(self, node:Node = None):
        name_offset = 0
        if node == None:
            node = self.__root_node
        else:
            name_offset = len(self.__name_block)
            self.__name_block += node.name().encode("utf-8")+b"\x00"
        node.set_name_offset(name_offset)
        node.set_id(self.__current_id)
        self.__current_id += 1
        
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
        count = 0
        for child in node.childs():
            if child.type() == FstTree.TYPE_DIR:
                count += self.__count_childs(child)
        return count + len(node.childs())
    def add_node_by_path(self, node_path:Path):
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
    def get_fst(self):
        self.__current_file_offset += self.__get_fst_length()
        self.__prepare()
        return self.__fst_block + self.__name_block


class BootBin:
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
    HEADER_LEN = 0x100
    HEADER_SECTIONLENTABLE_OFFSET = 0x90
    # Get total length using the sum of the 18 sections length and dol header length
    def get_dol_len(self, dolheader_data:bytes):
        dol_len = Dol.HEADER_LEN
        for i in range(18):
            dol_len += int.from_bytes(dolheader_data[Dol.HEADER_SECTIONLENTABLE_OFFSET+i*4:Dol.HEADER_SECTIONLENTABLE_OFFSET+(i+1)*4], "big", signed=False)
        return dol_len


# https://sudonull.com/post/68549-Gamecube-file-system-device
class Gcm:
    BI2BIN_LEN = 0x2000
    APPLOADER_HEADER_LEN = 0x20
    APPLOADER_OFFSET = 0x2440
    APPLOADERSIZE_OFFSET = 0x2454
    DVD_MAGIC = b"\xC2\x33\x9F\x3D"
    def unpack(self, iso_path:Path, folder_path:Path):
        with iso_path.open("rb") as iso_file:
            bootbin = BootBin(iso_file.read(BootBin.LEN))
            if bootbin.dvd_magic() != Gcm.DVD_MAGIC:
                raise Exception("Error - Invalid DVD format - this tool is for ISO/GCM files")

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
                raise Exception(f"Error - \"{folder_path}\" already exist. Remove this folder or use another name for the unpack folder.")
            
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
        if iso_path == None:
            iso_path = folder_path.parent / Path(folder_path.name).with_suffix(".iso")
        if iso_path.is_file():
            raise Exception(f"Error - {iso_path} already exist. Remove this file or use another GCM file name.")

        with iso_path.open("wb") as iso_file:
            sys_path = folder_path / "sys"
            logging.debug(f"{sys_path / 'boot.bin'}      -> {iso_path}(0x0:0x{BootBin.LEN:x})")
            logging.debug(f"{sys_path / 'bi2.bin'}       -> {iso_path}(0x{BootBin.LEN:x}:0x{Gcm.APPLOADER_OFFSET:x})")
            logging.debug(f"{sys_path / 'apploader.img'} -> {iso_path}(0x{Gcm.APPLOADER_OFFSET:x}:0x{Gcm.APPLOADER_OFFSET + (sys_path / 'apploader.img').stat().st_size:x}")
            
            bootbin = BootBin((sys_path / "boot.bin").read_bytes())
            iso_file.write(bootbin.data())
            iso_file.write((sys_path / "bi2.bin").read_bytes())
            iso_file.write((sys_path / "apploader.img").read_bytes())

            fstbin_offset = bootbin.fstbin_offset()
            fstbin_len = bootbin.fstbin_len()
            if (sys_path / "fst.bin").stat().st_size != fstbin_len:
                raise Exception(f"Error - Invalid fst.bin size in boot.bin offset 0x{BootBin.FSTLEN_OFFSET:x}:0x{BootBin.FSTLEN_OFFSET+4:x}!")
            logging.debug(f"{sys_path / 'fst.bin'}       -> {iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x})")
            iso_file.seek( fstbin_offset )
            fstbin_data = (sys_path / "fst.bin").read_bytes()
            iso_file.write( fstbin_data )
            
            dol_offset = bootbin.dol_offset()
            logging.debug(f"{sys_path / 'boot.dol'}      -> {iso_path}(0x{dol_offset:x}:0x{dol_offset + (sys_path / 'boot.dol').stat().st_size:x})")
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
                raise Exception(f"Error - Invalid file count inside {currentdir_path}. Use --rebuild-fst to update the FST before packing.")

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
                    file_offset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    file_len   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    if (currentdir_path / name).stat().st_size != file_len:
                        raise Exception(f"Error - Invalid file size: {currentdir_path / name} - use --rebuild-fst before packing files in the iso.")
                    logging.debug(f"{currentdir_path / name} -> {iso_path}(0x{file_offset:x}:0x{file_offset + file_len:x})")
                    iso_file.seek(file_offset)
                    iso_file.write( (currentdir_path / name).read_bytes() )
    def rebuild_fst(self, folder_path:Path, align:int):
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
        fst_path.write_bytes( fst_tree.get_fst() )

        fst_size = fst_path.stat().st_size
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.FSTLEN_OFFSET:x} with new fst size (0x{fst_size:x})")
        bootbin.set_fst_len(fst_size)
        logging.info(f"Patching {Path('sys/boot.bin')} offset 0x{BootBin.MAXFSTLEN_OFFSET:x} with new max fst size (0x{fst_size:x})")
        bootbin.set_max_fst_len(fst_size)

        (sys_path / "boot.bin").write_bytes(bootbin.data())


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='ISO/GCM packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-a', '--align', type=int, help='-a=10: alignment of files in the GCM ISO (default value is 4)', default=4)
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',   action='store_true', help="-p source_folder (dest_file.iso): Pack source_folder in new file source_folder.iso or dest_file.iso if specified")
    group.add_argument('-u', '--unpack', action='store_true', help='-u source_iso.iso (dest_folder): Unpack the GCM/ISO in new folder source_iso or dest_folder if specified')
    group.add_argument('-r', '--rebuild-fst', action='store_true', help='-r game_folder: Rebuild the game_folder/sys/fst.bin using files in game_folder/root')
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
        gcm.pack( p_input, p_output )
    elif args.unpack:
        logging.info("### Unpack GCM iso in new folder")
        gcm.unpack( p_input, p_output )
    elif args.rebuild_fst:
        logging.info("### Rebuilding FST and patching boot.bin")
        if args.align < 1:
            raise Exception("Error - Align must be > 0.")
        logging.info(f"Using alignment: {args.align}")
        gcm.rebuild_fst(p_input, args.align)
