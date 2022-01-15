#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import logging
import os
import time

__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


# http://wiki.xentax.com/index.php/GRAF:AFS_AFS
class Afs:
    MAGIC = b"AFS\x00"
    ALIGN = 0x800
    HEADER_LEN = 8
    FILENAMEBLOCK_ENTRY_LEN = 0x30
    __len = None
    __file_number = None
    __filenameblock_offset_offset = None
    __filenameblock_offset = None
    __filenameblock_len = None
    __filenameblock = None
    __tableofcontent = None
    def unpack(self, afs_path:Path, folder_path:Path):
        sys_path = folder_path / "sys"
        root_path = folder_path / "root"
        sys_path.mkdir(parents=True, exist_ok=True)
        root_path.mkdir(exist_ok=True)
        self.__len = afs_path.stat().st_size
        with afs_path.open("rb") as afs_file:
            self.__tableofcontent = afs_file.read(Afs.HEADER_LEN)
            if self.__get_magic() != Afs.MAGIC:
                raise Exception("Invalid AFS magic number")
            self.__file_number = int.from_bytes(self.__tableofcontent[4:8], "little")
            self.__tableofcontent += afs_file.read(self.__file_number*8)

            (self.__filenameblock_offset_offset, self.__filenameblock_offset) = self.__get_next_uint32(afs_file, Afs.HEADER_LEN+self.__file_number*8)
            afs_file.seek(self.__filenameblock_offset_offset+4)
            self.__filenameblock_len = int.from_bytes(afs_file.read(4), "little")
            
            if not self.__load_filenameblock(afs_file):
                logging.info("There is no filename block. Creating new names and dates for files.")
            else:
                logging.debug(f"Filenameblock offset:0x{self.__filenameblock_offset:x}, filenameblock len:0x{self.__filenameblock_len}.")
                afs_file.seek(len(self.__tableofcontent))
                self.__tableofcontent += afs_file.read(self.__filenameblock_offset_offset+8 - len(self.__tableofcontent))
                with (sys_path / "filenameblock.bin").open("wb") as filenameblock_file:
                    logging.info("Writting sys/filenameblock.bin")
                    filenameblock_file.write(self.__filenameblock)
            with (sys_path / "tableofcontent.bin").open("wb") as tableofcontent_file:
                logging.info("Writting sys/tableofcontent.bin")
                tableofcontent_file.write(self.__tableofcontent)
                self.__extract_files(root_path, afs_file)
    def pack(self, folder_path:Path, afs_path:Path = None):
        if afs_path == None:
            afs_path = folder_path / Path(folder_path.name).with_suffix(".afs")
        sys_path = folder_path / "sys"
        root_path = folder_path / "root"
        with afs_path.open("wb") as afs_file, (sys_path / "tableofcontent.bin").open("rb") as tableofcontent_file:
            logging.debug(f"Writting {sys_path}/tableofcontent.bin in AFS.")
            self.__tableofcontent = tableofcontent_file.read()
            self.__file_number = int.from_bytes(self.__tableofcontent[4:8], "little")
            afs_file.write(self.__pad(self.__tableofcontent))
            if (sys_path / "filenameblock.bin").is_file():
                (self.__filenameblock_offset_offset, self.__filenameblock_offset) = self.__get_next_uint32(tableofcontent_file, Afs.HEADER_LEN+self.__file_number*8, (sys_path / "tableofcontent.bin").stat().st_size)
                self.__filenameblock_len = int.from_bytes(self.__tableofcontent[self.__filenameblock_offset_offset+4:self.__filenameblock_offset_offset+8], "little")
                with (sys_path / "filenameblock.bin").open("rb") as filenameblock_file:
                    self.__filenameblock = filenameblock_file.read()
            for i in range(0, self.__file_number):
                file_offset = int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+i*8:Afs.HEADER_LEN+i*8+4], "little")
                file_len    = int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+i*8+4:Afs.HEADER_LEN+i*8+8], "little")
                if self.__filenameblock != None :
                    filename = self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN:i*Afs.FILENAMEBLOCK_ENTRY_LEN+32].split(b"\x00")[0].decode("utf-8")
                else:
                    filename = f"unknown_{i}.bin"
                with (root_path / filename).open("rb") as new_file:
                    logging.debug(f"Packing {root_path/filename} 0x{file_offset:x}:0x{file_offset+file_len:x} in iso.")
                    afs_file.seek(file_offset)
                    afs_file.write(self.__pad(new_file.read()))
            afs_file.write(self.__pad(self.__filenameblock))
    def rebuild(self, folder_path:Path):
        raise Exception("Not implemented yet")
    def list(self, path:Path):
        raise Exception("Not implemented yet")
        if path.is_file():
            self.__list_afs(path)
        else:
            self.__list_afsdir(path)
    def __pad(self, data:bytes):
        if len(data) % self.ALIGN != 0:
            data += b"\x00" * (self.ALIGN - (len(data) % self.ALIGN))
        return data
    def __extract_files(self, root_path:Path, afs_file):
        logging.info(f"Extracting {self.__file_number} files.")
        for i in range(0, self.__file_number):
            file_offset = int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+i*8:Afs.HEADER_LEN+i*8+4], "little")
            file_len    = int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+i*8+4:Afs.HEADER_LEN+i*8+8], "little")
            if self.__filenameblock != None :
                filename    = self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN:i*Afs.FILENAMEBLOCK_ENTRY_LEN+32].split(b"\x00")[0].decode("utf-8")
                year        = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+32:i*Afs.FILENAMEBLOCK_ENTRY_LEN+34], "little")
                month       = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+34:i*Afs.FILENAMEBLOCK_ENTRY_LEN+36], "little")
                day         = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+36:i*Afs.FILENAMEBLOCK_ENTRY_LEN+38], "little")
                hour        = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+38:i*Afs.FILENAMEBLOCK_ENTRY_LEN+40], "little")
                minute      = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+40:i*Afs.FILENAMEBLOCK_ENTRY_LEN+42], "little")
                second      = int.from_bytes(self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+42:i*Afs.FILENAMEBLOCK_ENTRY_LEN+44], "little")
                mtime = time.mktime(datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second).timetuple())
            else:
                filename = f"unknown_{i}.bin"
            with (root_path / filename).open("wb") as new_file:
                logging.debug(f"Writting {root_path/filename} 0x{file_offset:x}:0x{file_offset+file_len:x}")
                afs_file.seek(file_offset)
                new_file.write(afs_file.read(file_len))
            if self.__filenameblock != None :
                os.utime(root_path/filename, (mtime, mtime))
    def __load_filenameblock(self, afs_file):
        if self.__filenameblock_offset + self.__filenameblock_len > self.__len or self.__filenameblock_offset < self.__filenameblock_offset_offset:
            self.__clean_filenameblock()
            return False
        afs_file.seek(self.__filenameblock_offset)
        self.__filenameblock = afs_file.read(self.__filenameblock_len)

        if (len(self.__tableofcontent) - self.HEADER_LEN) / 8 != self.__filenameblock_len / Afs.FILENAMEBLOCK_ENTRY_LEN:
            self.__clean_filenameblock()
            return False

        for i in range(0, len(self.__tableofcontent)):
            if self.__tableofcontent[Afs.HEADER_LEN+i*8+4:Afs.HEADER_LEN+i*8+8] != self.__filenameblock[i*Afs.FILENAMEBLOCK_ENTRY_LEN+44:i*Afs.FILENAMEBLOCK_ENTRY_LEN+48]:
                self.__clean_filenameblock()
                return False
        return True
    def __clean_filenameblock(self):
        self.__filenameblock = None
        self.__filenameblock_offset = None
        self.__filenameblock_len = None
    def __get_magic(self):
        return self.__tableofcontent[0:4]
    # return a tuple with (offset:int, value:int)
    def __get_next_uint32(self, file, offset:int, file_len=None):
        if file_len == None:
            file_len = self.__len
        file.seek(offset)
        next_uint32 = int.from_bytes(file.read(4), "little")
        offset += 4
        if next_uint32 != 0:
            return (offset, next_uint32)
        # If filename_block_offset is not directly after the files offsets and lens
        # --> we search the next uint32 != 0
        while offset < file_len:
            max_size = 0x800
            if offset + max_size > file_len:
                max_size = file_len - offset
            tmp_block = file.read(max_size)
            for i in range(0, max_size, 4):
                next_uint32 = int.from_bytes(tmp_block[i:i+4], "little")
                if next_uint32 != 0:
                    return (offset+i, next_uint32)
            offset += max_size
        raise Exception("Empty AFS file.")
    def __list_afs(self, afs_path:Path):
        pass
    def __list_afsdir(self, root_dir:Path):
        pass


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='AFS packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',   action='store_true', help="-p source_folder (dest_file.afs) : Pack source_folder in new file source_folder.afs or dest_file.afs if specified")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_afs.afs (dest_folder) : Unpack the AFS in new folder source_afs or dest_folder if specified")
    group.add_argument('-l', '--list',   action='store_true', help="-l source_afs.afs or source_folder : List AFS files, length and offsets")
    group.add_argument('-r', '--rebuild', help="-r source_folder fndo_offset : Rebuild AFS tableofcontent and filenamedirectory using fndo_offset as filenamedirectory_offset_offset (the offset in the TOC)")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    afs = Afs()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        logging.info("### Pack in new AFS")
        if(p_output == Path(".")):
            p_output = Path(p_input.with_suffix(".afs"))
        logging.info(f"packing folder {p_input} in {p_output}")
        afs.pack( p_input, p_output )
    elif args.unpack:
        logging.info("### Unpack AFS in new folder")
        if p_output == Path("."):
            p_output = p_input.parent / p_input.stem
        logging.info(f"unpacking AFS {p_input} in {p_output}")
        afs.unpack( p_input, p_output )
    elif args.list:
        afs.list(p_input)
