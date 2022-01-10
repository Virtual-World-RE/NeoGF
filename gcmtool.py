#!/usr/bin/env python3
from pathlib import Path
import logging


__version__ = "0.0.5"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


DVD_MAGIC = b"\xC2\x33\x9F\x3D"
FST_TYPE_FILE = 0
FST_TYPE_DIR = 1

BOOTBIN_LEN = 0x440
BOOTBIN_DOLOFFSET_OFFSET = 0x420
BOOTBIN_FSTOFFSET_OFFSET = 0x424
BOOTBIN_FSTLEN_OFFSET = 0x428
BI2BIN_LEN = 0x2000
DOL_HEADER_LEN = 0x100
ISO_APPLOADER_OFFSET = 0x2440
ISO_APPLOADERSIZE_OFFSET = 0x2454
######################################################################
# Todo : add extension check ; add --disable-ignore
# -> test it on random iso and check that it's the same than dolphin extract
# -> test it !!!!
# add info on unused randoms bytes on initial DVD iso file
# -> that's why repack iso is different from initial iso
######################################################################
class Node:
    __id = None
    __type = None
    __name = None
    __offset_name = None
    def __init__(self, name:str, type):
        self.__name = name
        self.__type = type
    def id(self):             return self.__id
    def name(self):           return self.__name
    def offset_name(self):    return self.__offset_name
    def type(self):           return self.__type
    def set_id(self, id:int): self.id = id
    def set_offset_name(self, offset_name:int): self.__offset_name = offset_name


class File(Node):
    __size = None
    __offset = None
    def __init__(self, name:str, size:int):
        super().__init__(name, FST_TYPE_FILE)
        self.__size = size
    def __str__(self):
        return f"{self.id};{self.name()};{self.size()};{self.offset()};{self.offset_name()}"
    def size(self):                   return self.__size
    def offset(self):                 return self.__offset
    def set_offset(self, offset:int): self.__offset = offset 
    def format(self):
        return self.type().to_bytes(1, "big") + self.offset_name().to_bytes(3, "big") + self.offset().to_bytes(4, "big") + self.size().to_bytes(4, "big")


class Folder(Node):
    __parent = None
    __next_dir = None
    __childs = None
    def __init__(self, name:str, parent:Node):
        super().__init__(name, FST_TYPE_DIR)
        self.__parent = parent
        self.__childs = []
    def __str__(self):
        return f"{self.id};{self.name()};{self.next_dir()};{self.offset_name()}"
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
        return self.type().to_bytes(1, "big") + self.offset_name().to_bytes(3, "big") + self.parent().id.to_bytes(4, "big") + self.next_dir().to_bytes(4, "big")


class FstTree:
    __root_path_length = None
    __root_node = None
    __current_index = 0
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
        if node.type() == FST_TYPE_DIR:
            for child in node.childs():
                result += self.__to_str(child, depth+1)
        return result
    # Needed to know where we can begin to write files
    def __get_fst_length(self):
        self.__generate_nameblock_length()
        fst_len = self.__count_childs(self.__root_node)*12 + 12 + self.__nameblock_length
        if fst_len % self.__align != 0:
            fst_len += self.__align - (fst_len % self.__align)
        return fst_len
    def __generate_nameblock_length(self, node:Node = None):
        if node == None:
            node = self.__root_node
        else:
            self.__nameblock_length += len(node.name()) + 1
        if node.type() == FST_TYPE_DIR:
            for child in node.childs():
                self.__generate_nameblock_length(child)
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
    def __prepare(self, node:Node = None):
        offset_name = 0
        if node == None:
            node = self.__root_node
        else:
            offset_name = len(self.__name_block)
            self.__name_block += node.name().encode("utf-8")+b"\x00"
        node.set_offset_name(offset_name)
        node.set_id(self.__current_index)
        self.__current_index += 1
        
        if node.type() == FST_TYPE_DIR:
            node.set_next_dir(self.__current_index + self.__count_childs(node))
            if node == self.__root_node:
                self.__fst_block = b"\x01\x00\x00\x00\x00\x00\x00\x00" + node.next_dir().to_bytes(4, "big")
            else:
                self.__fst_block += node.format()
            for child in node.childs():
                self.__prepare(child)
        else:
            node.set_offset(self.__current_file_offset)
            self.__fst_block += node.format()
            self.__current_file_offset += node.size()
            if self.__current_file_offset % self.__align != 0:
                self.__current_file_offset += self.__align - (self.__current_file_offset % self.__align)
    def get_fst(self):
        self.__current_file_offset += self.__get_fst_length()
        self.__prepare()
        return self.__fst_block + self.__name_block
    def __count_childs(self, node:Folder):
        count = 0
        for child in node.childs():
            if child.type() == FST_TYPE_DIR:
                count += self.__count_childs(child)
        return count + len(node.childs())


class Dol:
    # Get total length using the sum of the 18 sections length and dol header length
    def get_dol_len(self, dolheader_data:bytes):
        dol_len = DOL_HEADER_LEN
        for i in range(18):
            dol_len += int.from_bytes(dolheader_data[0x90+i*4:0x90+(i+1)*4], "big", signed=False)
        return dol_len


# https://sudonull.com/post/68549-Gamecube-file-system-device
class GCM:
    def unpack(self, iso_path:Path, folder_path:Path):
        with iso_path.open("rb") as iso_file:
            bootbin_data = iso_file.read(BOOTBIN_LEN)
            if bootbin_data[0x1c:0x20] != DVD_MAGIC:
                raise Exception("Invalid DVD format - this tool is for ISO/GCM files")
            bi2bin_data = iso_file.read(BI2BIN_LEN)

            # https://www.gc-forever.com/wiki/index.php?title=Apploader
            # -> Full apploader size is sum of size and trailerSize, rounded up to 32 bytes.
            iso_file.seek(ISO_APPLOADERSIZE_OFFSET)
            size = int.from_bytes(iso_file.read(4), "big", signed=False)
            trailerSize = int.from_bytes(iso_file.read(4), "big", signed=False)
            
            # Dolphin Emulator add 32 Null bytes at the end of the extracted apploader.img
            apploader_size = size + trailerSize + 32
            
            iso_file.seek(ISO_APPLOADER_OFFSET)
            apploaderimg_data = iso_file.read(apploader_size)

            fstbin_offset = int.from_bytes(bootbin_data[BOOTBIN_FSTOFFSET_OFFSET:BOOTBIN_FSTOFFSET_OFFSET+4],"big", signed=False)
            fstbin_len = int.from_bytes(bootbin_data[BOOTBIN_FSTLEN_OFFSET:BOOTBIN_FSTLEN_OFFSET+4],"big", signed=False)
            iso_file.seek( fstbin_offset )
            fstbin_data = iso_file.read( fstbin_len )

            dol_offset = int.from_bytes(bootbin_data[BOOTBIN_DOLOFFSET_OFFSET:BOOTBIN_DOLOFFSET_OFFSET+4],"big", signed=False)
            iso_file.seek( dol_offset )
            dol = Dol()
            dolheader_data = iso_file.read(DOL_HEADER_LEN)
            dol_len = dol.get_dol_len( dolheader_data )
            bootdol_data = dolheader_data + iso_file.read( dol_len - DOL_HEADER_LEN )
            if folder_path != Path("."):
                base_path = folder_path
            else:
                base_path = Path(f"{bootbin_data[:4].decode('utf-8')}-{int.from_bytes(bootbin_data[6:7], 'little', signed=False):02}")
            
            logging.info(f"unpacking {iso_path} in {base_path}")
            sys_path = base_path / "sys"
            sys_path.mkdir(parents=True, exist_ok=True)

            with (sys_path / "boot.bin").open("wb") as bootbin_file, \
                 (sys_path / "bi2.bin" ).open("wb") as bi2bin_file, \
                 (sys_path / "fst.bin").open("wb") as fstbin_file, \
                 (sys_path / "apploader.img").open("wb") as apploaderimg_file,\
                 (sys_path / "boot.dol").open("wb") as bootdol_file:
                logging.debug(f"{iso_path}(0x0:0x{BOOTBIN_LEN:x}) -> {sys_path / 'boot.bin'}")
                bootbin_file.write(bootbin_data)
                logging.debug(f"{iso_path}(0x440:0x{ISO_APPLOADER_OFFSET:x}) -> {sys_path / 'bi2.bin'}")
                bi2bin_file.write(bi2bin_data)
                logging.debug(f"{iso_path}(0x{ISO_APPLOADER_OFFSET:x}:0x{ISO_APPLOADER_OFFSET + apploader_size:x} -> {sys_path / 'apploader.img'}")
                apploaderimg_file.write(apploaderimg_data)
                logging.debug(f"{iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x}) -> {sys_path / 'fst.bin'}")
                fstbin_file.write(fstbin_data)
                logging.debug(f"{iso_path}(0x{dol_offset:x}:0x{dol_offset + dol_len:x}) -> {sys_path / 'boot.dol'}")
                bootdol_file.write(bootdol_data)
            root_path = base_path / "root"
            root_path.mkdir(exist_ok=True)
            
            # And now we parse FST data to unpack all files in the GCM iso file
            dir_index_path = {0: root_path}
            currentdir_path = root_path

            # root: index=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when index reach next dir
            nextdir_arr = [ nextdir ]

            for index in range(1, base_names // 12):
                i = index * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                
                while index == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FST_TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_index_path[parentdir] / name
                    dir_index_path[index] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    with (currentdir_path / name).open("wb") as new_file:
                        iso_file.seek(fileoffset)
                        new_file.write( iso_file.read(filesize) )

                        logging.debug(f"{iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x}) -> {currentdir_path / name}")
    def pack(self, folder_path:Path, iso_path:Path = None):
        if iso_path == None:
            iso_path = folder_path.parent / Path(folder_path.name).with_suffix(".iso")
        with iso_path.open("wb") as iso_file, \
             (folder_path / "sys" / "boot.bin").open("rb") as bootbin_file, \
             (folder_path / "sys" / "bi2.bin" ).open("rb") as bi2bin_file, \
             (folder_path / "sys" / "fst.bin").open("rb") as fstbin_file, \
             (folder_path / "sys" / "apploader.img").open("rb") as apploaderimg_file,\
             (folder_path / "sys" / "boot.dol").open("rb") as bootdol_file :

            logging.debug(f"{folder_path / 'sys' / 'boot.bin'}      -> {iso_path}(0x0:0x{BOOTBIN_LEN:x})")
            logging.debug(f"{folder_path / 'sys' / 'bi2.bin'}       -> {iso_path}(0x{BOOTBIN_LEN:x}:0x{ISO_APPLOADER_OFFSET:x})")
            logging.debug(f"{folder_path / 'sys' / 'apploader.img'} -> {iso_path}(0x{ISO_APPLOADER_OFFSET:x}:0x{ISO_APPLOADER_OFFSET + (folder_path / 'sys' / 'apploader.img').stat().st_size:x}")
            
            bootbin_data = bootbin_file.read()
            iso_file.write( bootbin_data )
            iso_file.write(bi2bin_file.read())
            iso_file.write(apploaderimg_file.read())

            fstbin_offset = int.from_bytes(bootbin_data[BOOTBIN_FSTOFFSET_OFFSET:BOOTBIN_FSTOFFSET_OFFSET+4],"big", signed=False)
            fstbin_len = int.from_bytes(bootbin_data[BOOTBIN_FSTLEN_OFFSET:BOOTBIN_FSTLEN_OFFSET+4],"big", signed=False)
            if (folder_path / "sys" / "fst.bin").stat().st_size != fstbin_len:
                raise Exception("Invalid fst.bin size in boot.bin offset 0x{BOOTBIN_FSTLEN_OFFSET:x}:0x{BOOTBIN_FSTLEN_OFFSET+4:x}!")
            logging.debug(f"{folder_path / 'sys' / 'fst.bin'}       -> {iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x})")
            iso_file.seek( fstbin_offset )
            fstbin_data = fstbin_file.read()
            iso_file.write( fstbin_data )
            
            dol_offset = int.from_bytes(bootbin_data[BOOTBIN_DOLOFFSET_OFFSET:BOOTBIN_DOLOFFSET_OFFSET+4],"big", signed=False)
            logging.debug(f"{folder_path / 'sys' / 'boot.dol'}      -> {iso_path}(0x{dol_offset:x}:0x{dol_offset + (folder_path / 'sys' / 'boot.dol').stat().st_size:x})")
            iso_file.seek( dol_offset )
            iso_file.write( bootdol_file.read() )

            # Now parse fst.bin for writing files in the iso
            dir_index_path = {0: folder_path / "root"}
            currentdir_path = folder_path / "root"

            # root: index=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when index reach next dir
            nextdir_arr = [ nextdir ]

            for index in range(1, base_names // 12):
                i = index * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                
                while index == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FST_TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_index_path[parentdir] / name
                    dir_index_path[index] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    with (currentdir_path / name).open("rb") as new_file:
                        if (currentdir_path / name).stat().st_size != filesize:
                            raise Exception(f"Invalid file size : {currentdir_path / name} - use --rebuild-fst before packing files in the iso.")
                        logging.debug(f"{currentdir_path / name} -> {iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x})")
                        iso_file.seek(fileoffset)
                        iso_file.write( new_file.read() )
    def rebuild_fst(self, folder_path:Path, align:int):
        root_path = folder_path / "root"
        sys_path = folder_path / "sys"
        with (sys_path / "boot.bin").open("rb+") as bootbin_file:
            dol_offset = ISO_APPLOADER_OFFSET + (sys_path / "apploader.img").stat().st_size
            if dol_offset % align != 0:
                dol_offset += align - (dol_offset % align)
            logging.info(f"Patching sys/boot.bin offset 0x{BOOTBIN_DOLOFFSET_OFFSET:x} with new dol offset (0x{dol_offset:x})")
            bootbin_file.seek(BOOTBIN_DOLOFFSET_OFFSET)
            bootbin_file.write(dol_offset.to_bytes(4, "big"))
            
            fst_offset = dol_offset + (sys_path / "boot.dol").stat().st_size
            if fst_offset % align != 0:
                fst_offset += align - (fst_offset % align)
            logging.info(f"Patching sys/boot.bin offset 0x{BOOTBIN_FSTOFFSET_OFFSET:x} with new fst offset (0x{fst_offset:x})")
            bootbin_file.seek(BOOTBIN_FSTOFFSET_OFFSET)
            bootbin_file.write(fst_offset.to_bytes(4, "big"))
            
            fst_tree = FstTree(root_path, fst_offset, align=align)

            # Sorting paths approach original fst sort but specials chars are after and not before chars
            path_list = sorted([path for path in root_path.glob('**/*')], key=lambda s:Path(str(s).upper()))
            for path in path_list:
                fst_tree.add_node_by_path(path)
            logging.debug(fst_tree)
            fst_path = sys_path / "fst.bin"
            with fst_path.open("wb") as fstbin_file:
                logging.info("Writing fst in sys/fst.bin")
                fstbin_file.write( fst_tree.get_fst() )
            fst_size = fst_path.stat().st_size
            logging.info(f"Patching sys/boot.bin offset 0x{BOOTBIN_FSTLEN_OFFSET:x} with new fst size (0x{fst_size:x})")
            bootbin_file.seek(BOOTBIN_FSTLEN_OFFSET)
            bootbin_file.write(fst_size.to_bytes(4, "big"))


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='ISO/GCM packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-a', '--align', type=int, help='alignment of files in the GCM ISO 4 32000', default=4)
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',   action='store_true', help="-p source_folder (dest_file.iso) : Pack source_folder in new file source_folder.iso or dest_file.iso if specified")
    group.add_argument('-u', '--unpack', action='store_true', help='-u source_iso.iso (dest_folder) : Unpack the GCM/ISO in new folder source_iso or dest_folder if specified')
    group.add_argument('-r', '--rebuild-fst', action='store_true', help='-r game_folder : Rebuild the game_folder/sys/fst.bin using files in game_folder/root')
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    gcm = GCM()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        logging.info("### Pack")
        if(p_output == Path(".")):
            p_output = Path(p_input.with_suffix(".iso"))
        logging.info(f"packing folder {p_input} in {p_output}")
        gcm.pack( p_input, p_output )
    elif args.unpack:
        logging.info("### Unpack")
        gcm.unpack( p_input, p_output )
    elif args.rebuild_fst:
        logging.info("### Rebuilding FST")
        if args.align < 1:
            raise Exception("Align must be > 0")
        logging.info(f"Using alignment : {args.align}")
        gcm.rebuild_fst(p_input, args.align)
