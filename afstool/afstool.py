#!/usr/bin/env python3
from configparser import ConfigParser
from datetime import datetime
import logging
from math import ceil
import os
from pathlib import Path
import re
import time


__version__ = "0.1.2"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


# Not tested:
class AfsInvalidFileLenError(Exception): pass
class AfsEmptyAfsError(Exception): pass
class AfsInvalidFilenameDirectoryLengthError(Exception): pass
class AfsInvalidAfsFolderError(Exception): pass
# Tested:
class AfsInvalidMagicNumberError(Exception): pass
class AfsInvalidFilesRebuildStrategy(Exception): pass
class AfsFilenameDirectoryValueError(Exception): pass
class AfsInvalidFilePathError(Exception): pass
class AfsInvalidFieldsCountError(Exception): pass
class AfsIndexValueError(Exception): pass
class AfsIndexOverflowError(Exception): pass
class AfsIndexCollisionError(Exception): pass
class AfsOffsetValueError(Exception): pass
class AfsOffsetAlignError(Exception): pass
class AfsOffsetCollisionError(Exception): pass
class AfsFdOffsetOffsetValueError(Exception): pass
class AfsFdOffsetValueError(Exception): pass
class AfsFdLastAttributeTypeValueError(Exception): pass
class AfsFdOffsetCollisionError(Exception): pass
class AfsEmptyBlockValueError(Exception): pass
class AfsEmptyBlockAlignError(Exception): pass


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
        if (self.__sys_path / "filename_resolver.csv").is_file():
            self.__resolve_buffer = (self.__sys_path / "filename_resolver.csv").read_text()
            for line in self.__resolve_buffer.split('\n'):
                name_tuple = line.split(self.__separator)
                self.__names_tuples[name_tuple[1]] = int(name_tuple[0])
    def save(self):
        if len(self.__resolve_buffer) > 0:
            logging.info(f"Writting {Path('sys/filename_resolver.csv')}")
            (self.__sys_path / "filename_resolver.csv").write_text(self.__resolve_buffer[:-1])
    # resolve generate a unique filename when unpacking
    def resolve_new(self, fileindex:int, filename:str):
        if filename in self.__names_tuples:
            i = 1
            new_filename = f"{Path(filename).stem} ({i}){Path(filename).suffix}"
            while new_filename in self.__names_tuples:
                i+=1
                new_filename = f"{Path(filename).stem} ({i}){Path(filename).suffix}"
            self.__names_tuples[new_filename] = fileindex
            self.__resolve_buffer += f"{fileindex}{self.__separator}{new_filename}\n"
            return new_filename
        self.__names_tuples[filename] = fileindex
        return filename
    # Add new entry forcing the unpacked_filename²
    def add(self, fileindex:int, unpacked_filename:str):
        self.__names_tuples[unpacked_filename] = fileindex
        self.__resolve_buffer += f"{fileindex}{self.__separator}{unpacked_filename}\n"
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
    FILENAMEDIRECTORY_ENTRY_LEN = 0x30
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
        return self.__filenamedirectory[fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN:fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+32].split(b"\x00")[0].decode("utf-8")
    def __get_file_fdlast(self, fileindex:int):
        return int.from_bytes(self.__filenamedirectory[fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+44:fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+48], "little")
    def __get_file_mtime(self, fileindex:int):
        mtime_data = self.__filenamedirectory[fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+32:fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+44]
        year   = int.from_bytes(mtime_data[0:2], "little")
        month  = int.from_bytes(mtime_data[2:4], "little")
        day    = int.from_bytes(mtime_data[4:6], "little")
        hour   = int.from_bytes(mtime_data[6:8], "little")
        minute = int.from_bytes(mtime_data[8:10], "little")
        second = int.from_bytes(mtime_data[10:12], "little")
        return time.mktime(datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second).timetuple())
    def __patch_file_len(self, fileindex:int, file_len:int): # Patch file_len in the TOC
        self.__tableofcontent[Afs.HEADER_LEN+fileindex*8+4:Afs.HEADER_LEN+fileindex*8+8] = file_len.to_bytes(4, "little")
    def __patch_file_mtime(self, fileindex:int, mtime):
        mtime = datetime.fromtimestamp(mtime)
        self.__filenamedirectory[Afs.FILENAMEDIRECTORY_ENTRY_LEN*fileindex+32:Afs.FILENAMEDIRECTORY_ENTRY_LEN*fileindex+44] = \
            mtime.year.to_bytes(2,"little")+ \
            mtime.month.to_bytes(2,"little")+ \
            mtime.day.to_bytes(2,"little")+ \
            mtime.hour.to_bytes(2,"little")+ \
            mtime.minute.to_bytes(2,"little")+\
            mtime.second.to_bytes(2,"little")
    def __patch_fdlasts(self, fileindex:int, fd_last_attribute_type): # Patch FD last attributes according to the type
        if type(fd_last_attribute_type) == int: # every entry has the same const value
            self.__filenamedirectory[fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+44:fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+48] = fd_last_attribute_type.to_bytes(4, "little")
        elif fd_last_attribute_type == "length": # 
            self.__filenamedirectory[fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+44:fileindex*Afs.FILENAMEDIRECTORY_ENTRY_LEN+48] = self.__get_file_len(fileindex).to_bytes(4, "little")
        elif fd_last_attribute_type == "offset-length":
            # every odd index is changed according to the TOC lengths values with the serie: 0->updated_index=1 1->updated_index=3 2->updated_index=5
            # updated_index = index*2+1 with index*2+1 < self.__file_count
            updated_fdlast_index = fileindex*2+1
            if updated_fdlast_index < self.__file_count:
                self.__filenamedirectory[updated_fdlast_index*Afs.FILENAMEDIRECTORY_ENTRY_LEN+44:updated_fdlast_index*Afs.FILENAMEDIRECTORY_ENTRY_LEN+48] = self.__get_file_len(fileindex).to_bytes(4, "little")
        # fd_last_attribute_type == unknown
    def __pad(self, data:bytes):
        if len(data) % Afs.ALIGN != 0:
            data += b"\x00" * (Afs.ALIGN - (len(data) % Afs.ALIGN))
        return data
    def __clean_filenamedirectory(self):
        self.__filenamedirectory = None
        self.__filenamedirectory_offset = None
        self.__filenamedirectory_len = None
    def __loadsys_from_afs(self, afs_file, afs_len:int):
            self.__tableofcontent = afs_file.read(Afs.HEADER_LEN)
            if self.__get_magic() not in [Afs.MAGIC_00, Afs.MAGIC_20]:
                raise AfsInvalidMagicNumberError("Error - Invalid AFS magic number.")
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

            # This because we retrieve an int valid or not into fd offset
            if self.__filenamedirectory_offset is None:
                raise AfsEmptyAfsError("Error - Empty AFS.")

            afs_file.seek(self.__filenamedirectory_offset_offset+4)
            self.__filenamedirectory_len = int.from_bytes(afs_file.read(4), "little")

            # Test if offset of filenamedirectory is valid and if number of entries match between filenamedirectory and tableofcontent
            if self.__filenamedirectory_offset + self.__filenamedirectory_len > afs_len or \
               self.__filenamedirectory_offset < self.__filenamedirectory_offset_offset or \
               (tableofcontent_len - self.HEADER_LEN) / 8 != self.__filenamedirectory_len / Afs.FILENAMEDIRECTORY_ENTRY_LEN:
                self.__clean_filenamedirectory()
                return False

            afs_file.seek(self.__filenamedirectory_offset)
            self.__filenamedirectory = afs_file.read(self.__filenamedirectory_len)

            # Test if filename is correct by very basic pattern matching
            pattern = re.compile(b"^(?=.{32}$)[^\x00]+\x00+$")
            for i in range(self.__file_count):
                if not pattern.fullmatch(self.__filenamedirectory[i*Afs.FILENAMEDIRECTORY_ENTRY_LEN:i*Afs.FILENAMEDIRECTORY_ENTRY_LEN+32]):
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
                raise AfsInvalidFilenameDirectoryLengthError("Error - Tableofcontent filenamedirectory length does not match real filenamedirectory length.")
    def __print(self, title:str, lines_tuples, columns:list = list(range(7)), infos:str = ""):
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
    # return a list of offsets where files and sys files begin
    def __get_offsets_map(self):
        # offsets_map is used to check next used offset when updating files
        # we also check if there is intersect between files
        offsets_map = [(0, len(self.__tableofcontent))]
        for i in range(self.__file_count):
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
                raise AfsOffsetCollisionError(f"Error - Multiple files use same file offsets ranges.")
            last_tuple = offsets_tuple
            offsets_map[i] = offsets_tuple[0]
        return offsets_map
    # end offset not included (0,1) -> len=1
    def __get_formated_map(self):
        files_map = [("SYS TOC ", "00000000", f"{len(self.__tableofcontent):08x}", f"{len(self.__tableofcontent):08x}", "SYS TOC"+' '*12, "SYS TOC ", "SYS TOC")]

        for i in range(self.__file_count):
            file_offset = self.__get_file_offset(i)
            file_len    = self.__get_file_len(i)
            file_date   = datetime.fromtimestamp(self.__get_file_mtime(i)).strftime("%Y-%m-%d %H:%M:%S") if self.__filenamedirectory else " "*19
            filename    = self.__get_file_name(i) if self.__filenamedirectory else f"{i:08}"
            fdlast      = f"{self.__get_file_fdlast(i):08x}" if self.__filenamedirectory else " "*8
            files_map.append((f"{i:08x}", f"{file_offset:08x}", f"{file_offset + file_len:08x}", f"{file_len:08x}", file_date, fdlast, filename))

        if self.__filenamedirectory:
            files_map.append(("SYS FD  ", f"{self.__filenamedirectory_offset:08x}", \
                f"{self.__filenamedirectory_offset + len(self.__filenamedirectory):08x}", \
                f"{len(self.__filenamedirectory):08x}", "SYS FD"+' '*13, "SYS FD  ", "SYS FD"))
        return files_map
    def __get_fdlast_type(self):
        # Try to get the type of FD last attribute
        length_type = True
        offset_length_type = True
        constant_type = self.__get_file_fdlast(0)

        for i in range(self.__file_count):
            fd_last_attribute = self.__get_file_fdlast(i)
            if fd_last_attribute != self.__get_file_len(i):
                length_type = None
            if fd_last_attribute != self.__tableofcontent[8+i*4:8+i*4+4]:
                offset_length_type = None
            if fd_last_attribute != constant_type:
                constant_type = None
        if length_type: return "length"
        if offset_length_type: return "offset-length"
        if constant_type: return f"0x{constant_type:x}"
        logging.info("Unknown FD last attribute type.")
        return "unknown"
    def __write_rebuild_config(self, sys_path:Path, resolver:FilenameResolver):
        config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
        config.optionxform = str # makes options case sensitive
        config.add_section("Default")
        config.set("Default", "# Documentation available here: https://github.com/Virtual-World-RE/NeoGF/tree/main/afstool#afs_rebuildconf")
        config.set("Default", "AFS_MAGIC", f"0x{self.__get_magic().hex()}")
        config.set("Default", "files_rebuild_strategy", "mixed")
        config.set("Default", "filename_directory", "True" if self.__filenamedirectory else "False")
        if self.__filenamedirectory:
            config.add_section("FilenameDirectory")
            config.set("FilenameDirectory", "toc_offset_of_fd_offset", f"0x{self.__filenamedirectory_offset_offset:x}")
            config.set("FilenameDirectory", "fd_offset", f"0x{self.__filenamedirectory_offset:x}")
            config.set("FilenameDirectory", "fd_last_attribute_type", self.__get_fdlast_type())
        config.write((sys_path / "afs_rebuild.conf").open("w"))

        rebuild_csv = ""
        # generate and save afs_rebuild.csv
        for i in range(self.__file_count):
            filename = self.__get_file_name(i) if self.__filenamedirectory else f"{i:08}"
            unpacked_filename = resolver.resolve_from_index(i, filename) if self.__filenamedirectory else f"{i:08}"
            rebuild_csv += f"{unpacked_filename}/0x{i:x}/0x{self.__get_file_offset(i):x}/{filename}\n"
        if len(rebuild_csv) > 0:
            (sys_path / "afs_rebuild.csv").write_text(rebuild_csv[:-1])
    def unpack(self, afs_path:Path, folder_path:Path):
        sys_path = folder_path / "sys"
        root_path = folder_path / "root"
        sys_path.mkdir(parents=True)
        root_path.mkdir()

        resolver = None
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
            for i in range(self.__file_count):
                file_offset = self.__get_file_offset(i)
                file_len    = self.__get_file_len(i)
                filename    = resolver.resolve_new(i, self.__get_file_name(i)) if self.__filenamedirectory else f"{i:08}"
                
                logging.debug(f"Writting {root_path / filename} 0x{file_offset:x}:0x{file_offset + file_len:x}")
                afs_file.seek(file_offset)
                (root_path / filename).write_bytes(afs_file.read(file_len))

                if self.__filenamedirectory:
                    mtime = self.__get_file_mtime(i)
                    os.utime(root_path / filename, (mtime, mtime))

            if self.__filenamedirectory:
                resolver.save()
        self.__write_rebuild_config(sys_path, resolver)
    def pack(self, folder_path:Path, afs_path:Path = None):
        if afs_path is None:
            afs_path = folder_path / Path(folder_path.name).with_suffix(".afs")
        elif afs_path.suffix != ".afs":
            logging.warning("Dest file should have .afs file extension.")

        sys_path = folder_path / "sys"
        root_path = folder_path / "root"

        self.__loadsys_from_folder(sys_path)
        resolver = FilenameResolver(sys_path)
        offsets_map = self.__get_offsets_map()

        if self.__filenamedirectory:
            fd_last_attribute_type = self.__get_fdlast_type()
            if fd_last_attribute_type[:2] == "0x":
                fd_last_attribute_type = int(fd_last_attribute_type, 16)

        with afs_path.open("wb") as afs_file:
            # We update files
            for i in range(self.__file_count):
                file_offset = self.__get_file_offset(i)
                file_len    = self.__get_file_len(i)
                filename    = resolver.resolve_from_index(i, self.__get_file_name(i) if self.__filenamedirectory else f"{i:08}")

                file_path = root_path / filename
                new_file_len = file_path.stat().st_size
                
                if new_file_len != file_len:
                    # If no FD, we can raise AFS length without constraint
                    if offsets_map.index(file_offset) + 1 < len(offsets_map):
                        next_offset = offsets_map[offsets_map.index(file_offset)+1]
                        if file_offset + new_file_len > next_offset:
                            raise AfsInvalidFileLenError(f"File {file_path} as a new file_len giving an end offset (0x{file_offset + new_file_len:x}) > next file offset (0x{next_offset:x}). "\
                                "This means that we have to rebuild the AFS using -r and changing offset of all next files and this could lead to bugs if the main dol use AFS relative file offsets.")
                    self.__patch_file_len(i, new_file_len)
                    if self.__filenamedirectory:
                        self.__patch_fdlasts(i, fd_last_attribute_type)
                # If there is a filenamedirectory we update mtime:
                if self.__filenamedirectory:
                    self.__patch_file_mtime(i, round(file_path.stat().st_mtime))
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
        config = ConfigParser()
        root_path = folder_path / "root"
        sys_path  = folder_path / "sys"
        config.read(sys_path / "afs_rebuild.conf")
        if config["Default"]["AFS_MAGIC"] not in ["0x41465300", "0x41465320"]:
            raise AfsInvalidMagicNumberError("Error - Invalid [Default] AFS_MAGIC: must be 0x41465300 or 0x41465320.")
        if config["Default"]["files_rebuild_strategy"] not in ["index", "offset", "mixed", "auto"]:
            raise AfsInvalidFilesRebuildStrategy("Error - Invalid [Default] files_rebuild_strategy: must be index, offset, mixed or auto.")
        if config["Default"]["filename_directory"] not in ["True", "False"]:
            raise AfsFilenameDirectoryValueError("Error - Invalid [Default] filename_directory: must be True or False.")
       
        for path in [sys_path / "tableofcontent.bin", sys_path / "filenamedirectory.bin", sys_path / "filename_resolver.csv"]:
            if path.is_file():
                logging.info(f"Removing {path}.")
                path.unlink()

        files_paths = list(root_path.glob("*"))
        self.__file_count = len(files_paths)
        max_offset = None

        if config["Default"]["filename_directory"] == "True":
            if config["FilenameDirectory"]["toc_offset_of_fd_offset"] != "auto":
                if config["FilenameDirectory"]["toc_offset_of_fd_offset"][:2] != "0x" or len(config["FilenameDirectory"]["toc_offset_of_fd_offset"]) < 3:
                    raise AfsFdOffsetOffsetValueError("Error - Invalid [FilenameDirectory] toc_offset_of_fd_offset: must use hex format 0xabcdef or auto.")
                self.__filenamedirectory_offset_offset = int(config["FilenameDirectory"]["toc_offset_of_fd_offset"][2:], 16)
            else:
                self.__filenamedirectory_offset_offset = self.__file_count*8 + 8
            max_offset = int(ceil((self.__filenamedirectory_offset_offset + 8) / Afs.ALIGN)) * Afs.ALIGN # TOC length
            self.__filenamedirectory_len = self.__file_count * Afs.FILENAMEDIRECTORY_ENTRY_LEN

            if config["FilenameDirectory"]["fd_offset"] != "auto":
                if config["FilenameDirectory"]["fd_offset"][:2] != "0x" or len(config["FilenameDirectory"]["fd_offset"]) < 3:
                    raise AfsFdOffsetValueError("Error - Invalid [FilenameDirectory] fd_offset: must use hex format 0xabcdef or auto.")
                self.__filenamedirectory_offset = int(config["FilenameDirectory"]["fd_offset"][2:], 16)

            if config["FilenameDirectory"]["fd_last_attribute_type"] not in ["length", "offset-length", "unknown"]:
                if config["FilenameDirectory"]["fd_last_attribute_type"][0:2] != "0x" or len(config["FilenameDirectory"]["fd_last_attribute_type"]) < 3:
                    raise AfsFdLastAttributeTypeValueError("Error - Invalid [FilenameDirectory] fd_last_attribute_type: must be length, offset-length, 0xabcdef offset or unknown.")
        else:
            max_offset = int(ceil((self.__file_count*8 + 8) / Afs.ALIGN)) * Afs.ALIGN # TOC length

        self.__tableofcontent = bytearray.fromhex( config["Default"]["AFS_MAGIC"][2:] ) + self.__file_count.to_bytes(4, "little")
        files_rebuild_strategy = config["Default"]["files_rebuild_strategy"]

        csv_files_lists = []
        reserved_indexes = []
        empty_blocks_list = []

        # We parse the file csv and verify entries retrieving length for files
        if (sys_path / "afs_rebuild.csv").is_file():
            for line in (sys_path / "afs_rebuild.csv").read_text().split('\n'):
                line_splited = line.split('/')
                if len(line_splited) == 4:
                    unpacked_filename = line_splited[0]
                    index = None
                    if files_rebuild_strategy in ["index", "mixed"]:
                        if line_splited[1] != "auto":
                            index = line_splited[1]
                            if index[:2] != "0x" or len(index) < 3:
                                raise AfsIndexValueError(f"Error - Invalid entry index in afs_rebuild.csv: {index} - \"{line}\"")
                            index = int(index[2:], 16)
                            if index >= self.__file_count:
                                raise AfsIndexOverflowError(f"Error - Invalid entry index in afs_rebuild.csv: 0x{index:x} - \"{line}\" - index must be < files_count.")
                            if index in reserved_indexes:
                                raise AfsIndexCollisionError("Error - Multiple files using same index: 0x{index:x}")
                            reserved_indexes.append( index )

                    file_path = root_path / unpacked_filename
                    if not file_path.is_file():
                        raise AfsInvalidFilePathError(f"Error - File {file_path} doesn't exist.")
                    file_length = file_path.stat().st_size
                    
                    offset = None
                    if files_rebuild_strategy in ["offset", "mixed"]:
                        if line_splited[2] != "auto":
                            offset = line_splited[2]
                            if offset[:2] != "0x" or len(offset) < 3:
                                raise AfsOffsetValueError(f"Error - Invalid entry offset in afs_rebuild.csv: {offset} - \"{line}\"")
                            offset = int(offset[2:], 16)
                            if offset % Afs.ALIGN > 0:
                                raise AfsOffsetAlignError(f"Error - Invalid entry offset in afs_rebuild.csv: 0x{offset:x} - \"{line}\" - offset must be aligned to 0x800.")

                    csv_files_lists.append( [unpacked_filename, index, offset, line_splited[3], file_length] )

                    files_paths.remove( root_path / unpacked_filename )
                elif len(line_splited) == 2: # empty block
                    if line_splited[0][:2] != "0x" or line_splited[1][:2] != "0x" or len(line_splited[0]) < 3 or len(line_splited[1]) < 3:
                        raise AfsEmptyBlockValueError(f"Error - Invalid empty block values: \"{line}\"")
                    offset = int(line_splited[0][2:], 16)
                    length = int(line_splited[1][2:], 16)
                    if offset % Afs.ALIGN > 0 or length % Afs.ALIGN > 0:
                        raise AfsEmptyBlockAlignError(f"Error - Invalid empty block offset or length in afs_rebuild.csv: \"{line}\" - offset and length must be aligned to 0x800.")
                    empty_blocks_list.append([None, None, offset, None, length])
                else:
                    raise AfsInvalidFieldsCountError(f"Error - Invalid entry fields count in afs_rebuild.csv: \"{line}\"")

        # We generate file memory map with offsets:
        # available_space_ranges is then used to put files that have an adapted length
        # max_offset is used here to find memory collisions between files and next available space
        available_space_ranges = []
        tmp_ranges = empty_blocks_list
        if files_rebuild_strategy in ["offset", "mixed"]:
            tmp_ranges += csv_files_lists

        # We have to sort offsets before merging to avoid complex algorithm
        # TOC is already present with max_offset
        for file_tuple in sorted(tmp_ranges, key=lambda x: (x[2] is not None, x[2])):
            offset = file_tuple[2]
            if offset is None:
                continue
            if offset < max_offset:
                raise AfsOffsetCollisionError(f"Error - Offsets collision with offset \"0x{offset:x}\".")
            elif offset > max_offset:
                available_space_ranges.append( [max_offset, offset] )
            max_offset = int(ceil((offset + file_tuple[4]) / Afs.ALIGN)) * Afs.ALIGN

        for file_path in files_paths:
            csv_files_lists.append( [file_path.name, None, None, file_path.name, file_path.stat().st_size] )

        # sort by filename
        csv_files_lists.sort(key=lambda x: x[3])
        current_offset = max_offset
        
        # if index==None -> Assign an index not in reserved_indexes
        reserved_indexes.sort()
        next_index = 0
        for i in range(len(csv_files_lists)):
            if csv_files_lists[i][1] is None and files_rebuild_strategy in ["index", "mixed"] or files_rebuild_strategy in ["auto", "offset"]:
                for j in range(next_index, len(csv_files_lists)):
                    if j not in reserved_indexes:
                        next_index = j + 1
                        csv_files_lists[i][1] = j
                        break
        # sort by index
        csv_files_lists.sort(key=lambda x: x[1])

        # if offset==None -> Assign an offset in available_space_ranges or at the end of file allocated space
        for i in range(len(csv_files_lists)):
            if files_rebuild_strategy in ["offset", "mixed"] and csv_files_lists[i][2] is None or files_rebuild_strategy in ["auto", "index"]:
                block_len = int(ceil(csv_files_lists[i][4] / Afs.ALIGN)) * Afs.ALIGN
                for j in range(len(available_space_ranges)):
                    available_block_len = int(ceil((available_space_ranges[j][1] - available_space_ranges[j][0]) / Afs.ALIGN)) * Afs.ALIGN
                    if block_len <= available_block_len:
                        csv_files_lists[i][2] = available_space_ranges[j][0]
                        if block_len == available_block_len:
                            del available_space_ranges[j]
                        else:
                            available_space_ranges[j][0] += block_len
                        break
                else:
                    # Here we have a bigger file than available ranges so we pick current_offset at the end of allocated space
                    csv_files_lists[i][2] = current_offset
                    current_offset += block_len

        if self.__filenamedirectory_offset_offset:
            self.__filenamedirectory = b""
            fd_last_attribute_type = config["FilenameDirectory"]["fd_last_attribute_type"]
            if fd_last_attribute_type[:2] == "0x":
                fd_last_attribute_type = int(fd_last_attribute_type[2:], 16)

        # Have to be sorted by index
        # current_offset contains now fd offset if not already set
        resolver = FilenameResolver(sys_path)
        for i in range(len(csv_files_lists)):
            self.__tableofcontent += csv_files_lists[i][2].to_bytes(4, "little") + csv_files_lists[i][4].to_bytes(4, "little")
            # unpacked_filename, index, offset, filename, file_length
            if self.__filenamedirectory_offset_offset:
                mtime = b"\x00" * 12 # will be patched next pack
                fd_last_attribute = None
                if type(fd_last_attribute_type) == int:
                    fd_last_attribute = fd_last_attribute_type.to_bytes(4, "little")
                elif fd_last_attribute_type == "length":
                    fd_last_attribute = csv_files_lists[i][4].to_bytes(4, "little")
                elif fd_last_attribute_type == "offset-length":
                    fd_last_attribute = self.__tableofcontent[8+i*4:8+i*4+4]
                else: # == unknown
                    fd_last_attribute = b"\x00"*4
                self.__filenamedirectory += bytes(csv_files_lists[i][3], "utf-8").ljust(32, b"\x00") + mtime + fd_last_attribute
            # if unpacked_filename != filename we store it into the resolver
            if csv_files_lists[i][0] != csv_files_lists[i][3] or not self.__filenamedirectory_offset_offset:
                resolver.add(i, csv_files_lists[i][0])
        resolver.save()
        if self.__filenamedirectory:
            if not self.__filenamedirectory_offset:
                self.__filenamedirectory_offset = current_offset
            elif self.__filenamedirectory_offset < current_offset:
                raise AfsFdOffsetCollisionError(f"Error - Invalid FD offset 0x{self.__filenamedirectory_offset:x} < last used file block end 0x{current_offset:x}.")
            self.__tableofcontent = self.__tableofcontent.ljust(self.__filenamedirectory_offset_offset+8, b"\x00") # Add pad if needed
            self.__tableofcontent[self.__filenamedirectory_offset_offset:self.__filenamedirectory_offset_offset+8] = self.__filenamedirectory_offset.to_bytes(4, "little") + self.__filenamedirectory_len.to_bytes(4, "little")
            
            logging.info(f"Writting {Path('sys/filenamedirectory.bin')}")
            (sys_path / "filenamedirectory.bin").write_bytes(self.__filenamedirectory)
        logging.info(f"Writting {Path('sys/tableofcontent.bin')}")
        (sys_path / "tableofcontent.bin").write_bytes(self.__tableofcontent)
    def stats(self, path:Path):
        if path.is_file():
            with path.open("rb") as afs_file:
                self.__loadsys_from_afs(afs_file, path.stat().st_size)
        else:
            self.__loadsys_from_folder(path / "sys")

        files_map = self.__get_formated_map()
        files_map.sort(key=lambda x: x[1]) # sort by offset (str with fixed len=8)

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


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='AFS packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',    action='store_true', help="-p source_folder (dest_file.afs): Pack source_folder in new file source_folder.afs or dest_file.afs if specified.")
    group.add_argument('-u', '--unpack',  action='store_true', help="-u source_afs.afs (dest_folder): Unpack the AFS in new folder source_afs or dest_folder if specified.")
    group.add_argument('-s', '--stats',   action='store_true', help="-s source_afs.afs or source_folder: Get stats about AFS, files, memory, lengths and offsets.")
    group.add_argument('-r', '--rebuild', action='store_true', help="-r source_folder: Rebuild AFS tableofcontent (TOC) and filenamedirectory (FD) using afs_rebuild.conf file and afs_rebuild.csv.")
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
    elif args.rebuild:
        if not (p_input / "sys").is_dir():
            raise AfsInvalidAfsFolderError(f"Error - Invalid unpacked AFS: {p_input}.")
        logging.info(f"rebuilding {p_input}")
        afs.rebuild(p_input)
