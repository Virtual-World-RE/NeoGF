#!/usr/bin/env python3
from datetime import datetime
import logging
from math import ceil
import os
from pathlib import Path
import re
import time


__version__ = "0.0.4"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


class AfsInvalidFileLenError(Exception): pass


class FilenameResolver:
    __sys_path = None
    __names_tuples = None
    __resolve_buffer = ""
    __separator = '/'
    def __init__(self, sys_path:Path):
        self.__sys_path = sys_path
        self.__names_tuples = {}
        self.__load()
    def __load(self):
        if (self.__sys_path / "filename_resolver.txt").is_file():
            self.__resolve_buffer = (self.__sys_path / "filename_resolver.txt").read_text()
            for line in self.__resolve_buffer.split('\n'):
                name_tuple = line.split(self.__separator)
                self.__names_tuples[name_tuple[1]] = int(name_tuple[0])
    def save(self):
        if len(self.__resolve_buffer) > 0:
            logging.info("Writting filename_resolver.txt")
            (self.__sys_path / "filename_resolver.txt").write_text(self.__resolve_buffer[:-1])
    # resolve generate a unique filename when unpacking
    def resolve_new(self, fileindex:int, filename:str):
        if filename in self.__names_tuples:
            if self.__names_tuples[filename] == fileindex:
                return filename
            i = 1
            new_filename = f"{Path(filename).stem} ({i}){Path(filename).suffix}"
            while new_filename in self.__names_tuples:
                if self.__names_tuples[new_filename] == fileindex:
                    return new_filename
                i+=1
                new_filename = f"{Path(filename).stem} ({i}){Path(filename).suffix}"
            self.__names_tuples[new_filename] = fileindex
            self.__resolve_buffer += f"{fileindex}{self.__separator}{new_filename}\n"
            return new_filename
        self.__names_tuples[filename] = fileindex
        return filename
    # return generated filename if it exist else filename
    def resolve_from_index(self, fileindex:int, filename:str):
        for filename_key, fileindex_value in self.__names_tuples.items():
            if fileindex_value == fileindex:
                return filename_key
        return filename


# http://wiki.xentax.com/index.php/GRAF:AFS_AFS
class Afs:
    MAGIC_00 = b"AFS\x00"
    MAGIC_20 = b"AFS\x20"
    ALIGN = 0x800
    HEADER_LEN = 8
    FILENAMEBLOCK_ENTRY_LEN = 0x30
    __file_count = None
    __filenamedirectory_offset_offset = None
    __filenamedirectory_offset = None
    __filenamedirectory_len = None
    __filenamedirectory = None
    __tableofcontent = None
    def __get_magic(self):
        return bytes(self.__tableofcontent[0:4])
    def __get_file_count(self):
        return int.from_bytes(self.__tableofcontent[4:8], "little")
    def __get_filenamedirectory_offset(self):
        return int.from_bytes(self.__tableofcontent[self.__filenamedirectory_offset_offset:self.__filenamedirectory_offset_offset+4], "little")
    def __get_filenamedirectory_len(self):
        return int.from_bytes(self.__tableofcontent[self.__filenamedirectory_offset_offset+4:self.__filenamedirectory_offset_offset+8], "little")
    def __get_file_offset(self, fileindex:int):
        return int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+fileindex*8:Afs.HEADER_LEN+fileindex*8+4], "little")
    def __get_file_len(self, fileindex:int):
        return int.from_bytes(self.__tableofcontent[Afs.HEADER_LEN+fileindex*8+4:Afs.HEADER_LEN+fileindex*8+8], "little")
    def __get_file_name(self, fileindex:int):
        return self.__filenamedirectory[fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN:fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+32].split(b"\x00")[0].decode("utf-8")
    def __get_file_fdlast(self, fileindex:int):
        return int.from_bytes(self.__filenamedirectory[fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+44:fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+48], "little")
    def __get_mtime(self, fileindex:int):
        mtime_data = self.__filenamedirectory[fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+32:fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+44]
        year   = int.from_bytes(mtime_data[0:2], "little")
        month  = int.from_bytes(mtime_data[2:4], "little")
        day    = int.from_bytes(mtime_data[4:6], "little")
        hour   = int.from_bytes(mtime_data[6:8], "little")
        minute = int.from_bytes(mtime_data[8:10], "little")
        second = int.from_bytes(mtime_data[10:12], "little")
        return time.mktime(datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second).timetuple())
    def __patch_file_len(self, fileindex:int, file_len:int):
        # Patch file_len in the FD
        if self.__filenamedirectory:
            if self.__get_file_len(fileindex) == self.__filenamedirectory[fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+44:fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+48]:
                self.__filenamedirectory[fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+44:fileindex*Afs.FILENAMEBLOCK_ENTRY_LEN+48] = file_len.to_bytes(4, "little")
        # Patch file_len in the TOC
        self.__tableofcontent[Afs.HEADER_LEN+fileindex*8+4:Afs.HEADER_LEN+fileindex*8+8] = file_len.to_bytes(4, "little")
    def __patch_mtime(self, fileindex:int, mtime):
        mtime = datetime.fromtimestamp(mtime)
        self.__filenamedirectory[Afs.FILENAMEBLOCK_ENTRY_LEN*fileindex+32:Afs.FILENAMEBLOCK_ENTRY_LEN*fileindex+44] = \
            mtime.year.to_bytes(2,"little")+ \
            mtime.month.to_bytes(2,"little")+ \
            mtime.day.to_bytes(2,"little")+ \
            mtime.hour.to_bytes(2,"little")+ \
            mtime.minute.to_bytes(2,"little")+\
            mtime.second.to_bytes(2,"little")
    def __pad(self, data:bytes):
        if len(data) % self.ALIGN != 0:
            data += b"\x00" * (self.ALIGN - (len(data) % self.ALIGN))
        return data
    def __clean_filenamedirectory(self):
        self.__filenamedirectory = None
        self.__filenamedirectory_offset = None
        self.__filenamedirectory_len = None
    def __loadsys_from_afs(self, afs_file, afs_len:int):
            self.__tableofcontent = afs_file.read(Afs.HEADER_LEN)
            if self.__get_magic() not in [Afs.MAGIC_00, Afs.MAGIC_20]:
                raise Exception("Error - Invalid AFS magic number.")
            self.__file_count = self.__get_file_count()
            self.__tableofcontent += afs_file.read(self.__file_count*8)
            tableofcontent_len = len(self.__tableofcontent)

            offset = tableofcontent_len

            tmp_block = int.from_bytes(afs_file.read(4), "little")
            if tmp_block != 0:
                self.__filenamedirectory_offset_offset = offset
                self.__filenamedirectory_offset = tmp_block
            else:
                # If filenamedirectory_offset is not directly after the files offsets and lens
                # --> we search the next uint32 != 0
                offset += 4
                block_len = 0x800
                tmp_block = afs_file.read(block_len)
                while tmp_block:
                    match = re.search(b"^(?:\x00{4})*(?!\x00{4})(.{4})", tmp_block) # match next uint32
                    if match:
                        self.__filenamedirectory_offset_offset = offset + match.start(1)
                        self.__filenamedirectory_offset = int.from_bytes(match[1], "little")
                        break
                    offset += block_len
                    tmp_block = afs_file.read(block_len)

            if self.__filenamedirectory_offset is None:
                raise Exception("Error - Empty AFS.")

            afs_file.seek(self.__filenamedirectory_offset_offset+4)
            self.__filenamedirectory_len = int.from_bytes(afs_file.read(4), "little")

            # Test if offset of filenamedirectory is valid and if number of entries match between filenamedirectory and tableofcontent
            if self.__filenamedirectory_offset + self.__filenamedirectory_len > afs_len or \
               self.__filenamedirectory_offset < self.__filenamedirectory_offset_offset or \
               (tableofcontent_len - self.HEADER_LEN) / 8 != self.__filenamedirectory_len / Afs.FILENAMEBLOCK_ENTRY_LEN:
                self.__clean_filenamedirectory()
                return False

            afs_file.seek(self.__filenamedirectory_offset)
            self.__filenamedirectory = afs_file.read(self.__filenamedirectory_len)

            # Test if filename is correct by very basic pattern matching
            pattern = re.compile(b"^(?=.{32}$)[^\x00]+\x00+$")
            for i in range(0, self.__file_count):
                if not pattern.fullmatch(self.__filenamedirectory[i*Afs.FILENAMEBLOCK_ENTRY_LEN:i*Afs.FILENAMEBLOCK_ENTRY_LEN+32]):
                    self.__clean_filenamedirectory()
                    return False

            afs_file.seek(tableofcontent_len)
            self.__tableofcontent += afs_file.read(self.__filenamedirectory_offset_offset+8 - tableofcontent_len)
            return True
    def __loadsys_from_folder(self, sys_path:Path):
        self.__tableofcontent = bytearray( (sys_path / "tableofcontent.bin").read_bytes() )
        self.__file_count = self.__get_file_count()

        # If there is a filenamedirectory we load it
        if (sys_path / "filenamedirectory.bin").is_file():
            self.__filenamedirectory = bytearray((sys_path / "filenamedirectory.bin").read_bytes())
            self.__filenamedirectory_offset_offset = len(self.__tableofcontent) - 8
            self.__filenamedirectory_offset = self.__get_filenamedirectory_offset()
            self.__filenamedirectory_len = self.__get_filenamedirectory_len()
            if self.__filenamedirectory_len != len(self.__filenamedirectory):
                raise Exception("Error - Tableofcontent filenamedirectory length does not match real filenamedirectory length.")
    def unpack(self, afs_path:Path, folder_path:Path):
        sys_path = folder_path / "sys"
        root_path = folder_path / "root"
        sys_path.mkdir(parents=True)
        root_path.mkdir()

        with afs_path.open("rb") as afs_file:
            if not self.__loadsys_from_afs(afs_file, afs_path.stat().st_size):
                logging.info("There is no filename directory. Creating new names and dates for files.")
            else:
                logging.debug(f"filenamedirectory_offset:0x{self.__filenamedirectory_offset:x}, filenamedirectory_len:0x{self.__filenamedirectory_len:x}.")
                logging.info(f"Writting {Path('sys/filenamedirectory.bin')}")
                (sys_path / "filenamedirectory.bin").write_bytes(self.__filenamedirectory)
                resolver = FilenameResolver(sys_path)

            logging.info(f"Writting {Path('sys/tableofcontent.bin')}")
            (sys_path / "tableofcontent.bin").write_bytes(self.__tableofcontent)

            logging.info(f"Extracting {self.__file_count} files.")
            for i in range(0, self.__file_count):
                file_offset = self.__get_file_offset(i)
                file_len    = self.__get_file_len(i)
                filename    = resolver.resolve_new(i, self.__get_file_name(i)) if self.__filenamedirectory else f"{i:08}"
                
                logging.debug(f"Writting {root_path / filename} 0x{file_offset:x}:0x{file_offset + file_len:x}")
                afs_file.seek(file_offset)
                (root_path / filename).write_bytes(afs_file.read(file_len))

                if self.__filenamedirectory:
                    mtime = self.__get_mtime(i)
                    os.utime(root_path / filename, (mtime, mtime))
            if self.__filenamedirectory:
                resolver.save()
    def pack(self, folder_path:Path, afs_path:Path = None):
        if afs_path == None:
            afs_path = folder_path / Path(folder_path.name).with_suffix(".afs")
        elif afs_path.suffix != ".afs":
            logging.warning("Dest file should have .afs file extension.")

        sys_path = folder_path / "sys"
        root_path = folder_path / "root"

        self.__loadsys_from_folder(sys_path)

        if self.__filenamedirectory:
            resolver = FilenameResolver(sys_path)

        offsets_map = self.__get_offsets_map()
        with afs_path.open("wb") as afs_file:
            # We update files
            for i in range(0, self.__file_count):
                file_offset = self.__get_file_offset(i)
                file_len    = self.__get_file_len(i)
                filename    = resolver.resolve_from_index(i, self.__get_file_name(i)) if self.__filenamedirectory else f"{i:08}"

                file_path = root_path / filename
                new_file_len = file_path.stat().st_size
                
                if new_file_len != file_len:
                    next_offset = None
                    # If no FD, we can raise AFS length without constraint
                    if offsets_map.index(file_offset) + 1 < len(offsets_map):
                        next_offset = offsets_map[offsets_map.index(file_offset)+1]
                    if next_offset:
                        if file_offset + new_file_len > next_offset:
                            raise AfsInvalidFileLenError(f"File {file_path} as a new file_len (0x{new_file_len:x}) > next file offset (0x{next_offset:x}). "\
                                "This means that we have to rebuild the AFS using -r and changing offset of all next files and this could lead to bugs if the main dol use AFS relative file offsets.")
                    self.__patch_file_len(i, new_file_len)
                # If there is a filenamedirectory we update mtime:
                if self.__filenamedirectory:
                    self.__patch_mtime(i, round(file_path.stat().st_mtime))
                logging.debug(f"Packing {file_path} 0x{file_offset:x}:0x{file_offset+new_file_len:x} in AFS.")
                afs_file.seek(file_offset)
                afs_file.write(self.__pad(file_path.read_bytes()))
            if self.__filenamedirectory:
                afs_file.seek(self.__filenamedirectory_offset)
                afs_file.write(self.__pad(self.__filenamedirectory))
            logging.debug(f"Packing {sys_path / 'tableofcontent.bin'} at the beginning of the AFS.")
            afs_file.seek(0)
            afs_file.write(self.__tableofcontent)
    def rebuild(self, folder_path:Path):
        raise Exception("Error - Not implemented yet")
    def stats(self, path:Path):
        if path.is_file():
            with path.open("rb") as afs_file:
                self.__loadsys_from_afs(afs_file, path.stat().st_size)
        else:
            self.__loadsys_from_folder(path / "sys")

        files_map = self.__get_formated_map()
        files_map.sort(key=lambda x: x[1]) # sort by offset

        # Offsets intersect
        dup_offsets_tuples = []
        last_tuple = (-1, "-1", "0") # empty space search init
        new_set = True
        # Filenames duplicates
        dup_names_dict = {} # tmp dict for grouping by filename
        dup_names_tuples = []
        # For empty blocks
        empty_space_tuples = []
        for file_tuple in files_map:
            # Filenames duplicates
            if not file_tuple[6] in dup_names_dict:
                dup_names_dict[file_tuple[6]] = [file_tuple]
            else:
                dup_names_dict[file_tuple[6]].append(file_tuple)
            # Offsets intersect
            if file_tuple[1] < last_tuple[1]:
                if new_set:
                    dup_offsets_tuples.append("Files sharing same offsets:\n")
                    new_set = False
                dup_offsets_tuples.append(file_tuple)
            else:
                new_set = True
            # Empty blocks
            last_block_end = ceil(int(last_tuple[2], base=16) / Afs.ALIGN) * Afs.ALIGN
            if int(file_tuple[1], base=16) - last_block_end >= Afs.ALIGN:
                empty_space_tuples.append( (last_tuple[2], file_tuple[1], f"{int(file_tuple[1], base=16) - int(last_tuple[2], base=16):08x}", file_tuple[6]) )
            last_tuple = file_tuple

        for filename in dup_names_dict:
            if len(dup_names_dict[filename]) > 1:
                dup_names_tuples += ["Files sharing same name:\n"] + [file_tuple for file_tuple in dup_names_dict[filename]]

        dup_offsets = "Yes" if len(dup_offsets_tuples) > 1 else "No"
        dup_names   = "Yes" if len(dup_names_tuples) > 1 else "No"
        empty_space = "Yes" if len(empty_space_tuples) > 1 else "No"

        files_info =  f"AFS Magic/Version                : {str(self.__get_magic())[2:-1]}\n"
        files_info += f"TOC offset of the FD offset      : 0x{self.__filenamedirectory_offset_offset:x}\n" if self.__filenamedirectory else ""
        files_info += f"Multiple files using same offsets: {dup_offsets}\n"
        files_info += f"Multiple files using same name   : {dup_names}\n" if self.__filenamedirectory else ""
        files_info += f"Empty blocks                     : {empty_space}\n"
        self.__print("Global infos and AFS space mapping:", files_map, infos=files_info)
        if dup_offsets_tuples:
            self.__print("Files sharing same AFS offsets:", dup_offsets_tuples)
        if dup_names_tuples:
            self.__print("Files using same filenames:", dup_names_tuples)
        if empty_space_tuples:
            self.__print("Empty blocks between files (filename = name of the previous file):", empty_space_tuples, columns=[1,2,3,6])
    def __print(self, title:str, lines_tuples, columns:list = list(range(0,7)), infos:str = ""):
        stats_buffer = "#"*100+f"\n# {title}\n"+"#"*100+f"\n{infos}|"+"-"*99+"\n"
        if 0 in columns: stats_buffer += "| Index    ";
        if 1 in columns: stats_buffer += "| b offset ";
        if 2 in columns: stats_buffer += "| e offset ";
        if 3 in columns: stats_buffer += "| length   ";
        if 4 in columns: stats_buffer += "| YYYY-mm-dd HH:MM:SS ";
        if 5 in columns: stats_buffer += "| FD last  ";
        if 6 in columns: stats_buffer += "| Filename";
        stats_buffer += "\n|"+"-"*99+"\n"
        for line in lines_tuples:
            stats_buffer += line if type(line) == str else "| "+" | ".join(line)+"\n"
        print(stats_buffer, end='')
    # end offset not included (0,1) -> len=1
    def __get_offsets_map(self):
        # offsets_map is used to check next used offset when updating files
        # we also check if there is intersect between files
        offsets_map = [(0, len(self.__tableofcontent))]
        for i in range(0, self.__file_count):
            file_offset = self.__get_file_offset(i)
            offsets_map.append( (file_offset, file_offset + self.__get_file_len(i)) )
        if self.__filenamedirectory:
            filenamedirectory_offset = self.__get_filenamedirectory_offset()
            offsets_map.append( (filenamedirectory_offset, filenamedirectory_offset + self.__get_filenamedirectory_len()) )
        offsets_map.sort(key=lambda x: x[0])

        # Check if there is problems in file memory mapping
        last_tuple = (-1, -1)
        for i, offsets_tuple in enumerate(offsets_map):
            if offsets_tuple[0] < last_tuple[1]:
                raise Exception(f"Error - Multiple files use same file offsets ranges.")
            last_tuple = offsets_tuple
            offsets_map[i] = offsets_tuple[0]
        return offsets_map
    # end offset not included (0,1) -> len=1
    def __get_formated_map(self):
        files_map = [("SYS TOC ", "00000000", f"{len(self.__tableofcontent):08x}", f"{len(self.__tableofcontent):08x}", "SYS TOC"+' '*12, "SYS TOC ", "SYS TOC")]

        for i in range(0, self.__file_count):
            file_offset = self.__get_file_offset(i)
            file_len    = self.__get_file_len(i)
            file_date   = datetime.fromtimestamp(self.__get_mtime(i)).strftime("%Y-%m-%d %H:%M:%S") if self.__filenamedirectory else " "*19
            filename    = self.__get_file_name(i) if self.__filenamedirectory else f"{i:08}"
            fdlast      = f"{self.__get_file_fdlast(i):08x}" if self.__filenamedirectory else " "*8
            files_map.append((f"{i:08x}", f"{file_offset:08x}", f"{file_offset + file_len:08x}", f"{file_len:08x}", file_date, fdlast, filename))

        if self.__filenamedirectory:
            files_map.append(("SYS FD  ", f"{self.__filenamedirectory_offset:08x}", \
                f"{self.__filenamedirectory_offset + len(self.__filenamedirectory):08x}", \
                f"{len(self.__filenamedirectory):08x}", "SYS FD"+' '*13, "SYS FD  ", "SYS FD"))
        return files_map


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='AFS packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',   action='store_true', help="-p source_folder (dest_file.afs): Pack source_folder in new file source_folder.afs or dest_file.afs if specified.")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_afs.afs (dest_folder): Unpack the AFS in new folder source_afs or dest_folder if specified.")
    group.add_argument('-s', '--stats',   action='store_true', help="-s source_afs.afs or source_folder: Get stats about AFS, files, memory, lengths and offsets.")
    group.add_argument('-r', '--rebuild', help="-r source_folder: Rebuild AFS tableofcontent (TOC) and filenamedirectory (FD) using rebuild.conf file.")
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
    elif args.stats:
        afs.stats(p_input)
