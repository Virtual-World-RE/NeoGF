#!/usr/bin/env python3
import afstool
from configparser import ConfigParser
import copy
import os
from pathlib import Path
import shutil
from time import time
from datetime import datetime


__version__ = "0.0.7"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


##################################################
# Set afss_path with your AFSs folder
# Set afspacker_path with the path of AFSPacker.exe
##################################################
afss_path = Path("afs")
afspacker_path = Path("../_autres/_soft/AFSPacker.exe")

afspacker_unpack_path = Path("afspacker_unpack")
# Created tmp paths
unpack_path  = Path("unpack")
unpack2_path = Path("unpack2")
repack_path  = Path("repack")


def test_storage():
    total, used, free = shutil.disk_usage("/")
    if free - 10**10 < 3 * sum(path.stat().st_size for path in afss_path.glob('*') if path.is_file()):
        raise Exception("Error - Not enought free space on the disk to run tests.")


# Need to know offsets of TOC to get the max length of files
# and unpacked names of files when duplicated
class AfsTest(afstool.Afs):
    # return a list of tuples with (offset, resolved filename)
    def get_range(self, folder_path:Path):
        sys_path = folder_path / "sys"
        self._Afs__loadsys_from_folder(sys_path)
        resolver = afstool.FilenameResolver(sys_path)

        offsets_names_map = [(0, "SYS TOC")]
        for i in range(self._Afs__file_count):
            filename = resolver.resolve_from_index(i, self._Afs__get_file_name(i)) if self._Afs__filenamedirectory else f"{i:08}"
            offsets_names_map.append( (self._Afs__get_file_offset(i), filename) )
        if self._Afs__filenamedirectory:
            offsets_names_map.append( (self._Afs__get_filenamedirectory_offset(), "SYS FD") )
        return offsets_names_map


def print_paths_differences(folder1_paths:list, folder2_paths:list):
    backup_paths = folder2_paths.copy()
    for path in folder1_paths:
        if path in folder2_paths:
            folder2_paths.remove(path)
    for path in backup_paths:
        if path in folder1_paths:
            folder1_paths.remove(path)
    print("folder1 diff:")
    for path in folder1_paths:
        print(path)
    print("folder2 diff:")
    for path in folder2_paths:
        print(path)


# compare two files
def compare_files(file1_path:Path, file2_path:Path):
    CLUSTER_LEN = 131072
    with file1_path.open("rb") as file1, file2_path.open("rb") as file2:
        # Init
        bytes1 = file1.read(CLUSTER_LEN)
        bytes2 = file2.read(CLUSTER_LEN)
        while bytes1 or bytes2: # continue if bytes1 and bytes2 have a len > 0
            if bytes1 != bytes2:
                return False
            bytes1 = file1.read(CLUSTER_LEN)
            bytes2 = file2.read(CLUSTER_LEN)
    return True


# compare two folder
#     -> raise an exception if there is a difference in paths or in file content
def compare_folders(folder1: Path, folder2: Path, compare_mtime:bool = False):
    folder1_tmp_paths = list(folder1.glob("*"))
    folder1_file_count = len(folder1_tmp_paths)
    print(f"compare \"{folder1}\" - \"{folder2}\" ({folder1_file_count} files)")
    if folder1_file_count == 0:
        raise Exception(f"Error - Empty folder: {folder1}")

    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names in filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in folder1_tmp_paths]
    folder2_paths = [Path(*path.parts[len2:]) for path in folder2.glob("*")]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Error - Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")
    # 2. Compare files content
    for path1 in folder1_tmp_paths:
        path2 = folder2 / Path(*path1.parts[len1:])
        if compare_mtime:
            if round(path1.stat().st_mtime) != round(path2.stat().st_mtime):
                raise Exception(f"Error - \"{path1}\" and \"{path2}\" mtime (update time) are different:\n    {round(path1.stat().st_mtime)}-{round(path2.stat().st_mtime)}")
        if not compare_files(path1, path2):
            raise Exception(f"Error - \"{path1}\" and \"{path2}\" are different.")


# compare two AFS
#     -> raise an exception if there is a difference in:
#            -paths
#            -files content
#            -mtime if there is a filename directory
def compare_unpacked_AFS(folder1: Path, folder2: Path):
    compare_mtime = False
    if (folder1 / "sys" / "filenamedirectory.bin").is_file():
        compare_mtime = True
    compare_folders(folder1 / "root", folder2 / "root", compare_mtime)


def patch_all_bytes(file_path:Path, max_len:int = None):
    file_data = bytearray(file_path.read_bytes())
    if max_len is None:
        max_len = len(file_data)
    elif max_len < len(file_data):
        file_data = file_data[:max_len]
    for i in range(len(file_data)):
        file_data[i] = (file_data[i] + 1) % 255
    if max_len > len(file_data):
        file_data.extend(b"\x01"*(max_len - len(file_data)))
    file_path.write_bytes(file_data)


# if not bool_len: patch all files with max len
# if bool_len: patch first file found with max len + 1
def patch_unpackedfiles_in_folder(folder_path:Path, bool_len:bool = False):
    for afsfolder_path in folder_path.glob("*"):
        print(f"Patching {afsfolder_path}...")
        afs_test = AfsTest()
        offsets_names_map = afs_test.get_range(afsfolder_path)

        for file_path in afsfolder_path.glob("root/*"):
            max_len = None
            # Search by resolved name and get begin offset of next file / SYS File
            for i in range(len(offsets_names_map)):
                if offsets_names_map[i][1] == file_path.name:
                    if i+1 < len(offsets_names_map):
                        max_len = offsets_names_map[i+1][0] - offsets_names_map[i][0]
                        if bool_len:
                            max_len += 1
                    # else there is no limit because last file
                    else:
                        max_len = file_path.stat().st_size + afstool.Afs.ALIGN
                    break
            patch_all_bytes(file_path, max_len)
            if bool_len:
                break


def repack_unpack2_compare():
    repack_path.mkdir()
    unpack2_path.mkdir()
    unpack_paths = list(unpack_path.glob("*"))

    # repack unpack_path repack_path
    for folder_path in unpack_paths:
        afstool_pack(folder_path, repack_path / Path(folder_path.stem).with_suffix('.afs'))

    # unpack repack_path unpack2_path
    for afs_path in repack_path.glob("*"):
        afstool_unpack(afs_path, unpack2_path / afs_path.stem)

    shutil.rmtree(repack_path)

    # compare unpack_path unpack2_path
    for folder_path in unpack_paths:
        compare_unpacked_AFS(folder_path, unpack2_path / folder_path.name)

    shutil.rmtree(unpack2_path)


# generate an unpacked AFS filesys for testing
# files are filled with 0xff
def mk_rebuild_filesys(unpacked_path:Path, files:list, afs_rebuild_conf:dict, afs_rebuild_csv:str = ""):
    sys_path = unpacked_path / "sys"
    root_path = unpacked_path / "root"
    sys_path.mkdir(parents=True)
    root_path.mkdir()

    # create files
    for file_tuple in files:
        (root_path / file_tuple[0]).write_bytes(b"\xff" * file_tuple[1])

    # create afs_config.conf
    conf_txt = f"[Default]\n"\
        f"AFS_MAGIC = {afs_rebuild_conf['Default']['AFS_MAGIC']}\n"\
        f"files_rebuild_strategy = {afs_rebuild_conf['Default']['files_rebuild_strategy']}\n"\
        f"filename_directory = {afs_rebuild_conf['Default']['filename_directory']}\n\n"
    if afs_rebuild_conf["Default"]["filename_directory"] == "True":
        conf_txt += f"[FilenameDirectory]\n\n"\
            f"toc_offset_of_fd_offset = {afs_rebuild_conf['FilenameDirectory']['toc_offset_of_fd_offset']}\n"\
            f"fd_offset = {afs_rebuild_conf['FilenameDirectory']['fd_offset']}\n"\
            f"fd_last_attribute_type = {afs_rebuild_conf['FilenameDirectory']['fd_last_attribute_type']}\n"
    (sys_path / "afs_rebuild.conf").write_text(conf_txt)
    if len(afs_rebuild_csv) > 0:
        (sys_path / "afs_rebuild.csv").write_text(afs_rebuild_csv)


def test_except(afs_rebuild_conf:dict, exception, rebuild_csv_data=""):
    global i
    i += 1
    rebuild_path = unpack_path / f"rebuild_{i:03}"
    mk_rebuild_filesys(rebuild_path, [("a.bin", 0x500),("b.bin", 0x600),("c.bin", 0x700)], afs_rebuild_conf, rebuild_csv_data)
    a = afstool.Afs()
    try:
        a.rebuild(rebuild_path)
        raise Exception(f"Error while rebuilding {rebuild_path}.")
    except exception:
        print(f"Valid {exception.__name__} check.")


def test_rebuild_repack(afs_rebuild_conf:dict, files:list, raw_data:bytes, rebuild_csv_data:str = "", raw_fd_data:bytes = None):
    global i
    i += 1
    rebuild_path = unpack_path / f"rebuild_{i:03}"
    mk_rebuild_filesys(rebuild_path, files, afs_rebuild_conf, rebuild_csv_data)

    rebuilded_repack_path = repack_path / Path(rebuild_path.stem).with_suffix(".afs")
    a = afstool.Afs()
    a.rebuild(rebuild_path)
    # Retrieve FD dates for each files
    if afs_rebuild_conf["Default"]["filename_directory"] == "True":
        raw_fd_data = bytearray(raw_fd_data)
        for j in range(0, len(raw_fd_data), 48):
            mtime = datetime.fromtimestamp(round((rebuild_path / "root" / (raw_fd_data[j:j+32]).split(b"\x00")[0].decode("utf-8")).stat().st_mtime))
            raw_fd_data[j+32:j+32+12] = mtime.year.to_bytes(2,"little")+mtime.month.to_bytes(2,"little")+mtime.day.to_bytes(2,"little")+\
                mtime.hour.to_bytes(2,"little")+mtime.minute.to_bytes(2,"little")+mtime.second.to_bytes(2,"little")
        raw_data += raw_fd_data.ljust(0x800, b"\x00")
    a.pack(rebuild_path, rebuilded_repack_path)
    if rebuilded_repack_path.read_bytes() != raw_data:
        raise Exception(f"Error - Not the expected repack {rebuilded_repack_path}.")
    print(f"Success - {rebuild_path}.")


def list_bytes(l:list): return b"".join(list(map(lambda x: x.to_bytes(4,"little"), l)))


##################################################
# afstool.py commands wrappers
##################################################
def afspacker_extract(afs_path:Path, folder_path:Path):
    print(f"AFSPacker.exe: Extracting \"{afs_path}\" in \"{folder_path}\"")
    if os.system(f"{afspacker_path} -e \"{afs_path}\" \"{folder_path}\" > NUL") != 0:
        raise Exception("Error while unpacking with AFSPacker.exe")
def afstool_pack(folder_path:Path, afs_path:Path):
    if os.system(f"python afstool.py -p \"{folder_path}\" \"{afs_path}\"") != 0:
        raise Exception("Error while (re)packing.")
def afstool_unpack(afs_path:Path, folder_path:Path):
    if os.system(f"python afstool.py -u \"{afs_path}\" \"{folder_path}\"") != 0:
        raise Exception("Error while unpacking.")
def afstool_stats(path:Path):
    if os.system(f"python afstool.py -s \"{path}\" > NUL") != 0:
        raise Exception("Error while getting stats.")
def afstool_rebuild(folder_path:Path):
    if os.system(f"python afstool.py -r \"{folder_path}\"") != 0:
        raise Exception("Error while rebuilding.")


TEST_COUNT = 10

start = time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or unpack2_path.is_dir() or repack_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{unpack2_path}\n-{repack_path}")

test_storage()

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Comparing afss_path->unpack->[unpack_path] AFS with [afspacker_unpack_path].")
print("###############################################################################")
unpack_path.mkdir()
afss_paths = list(afss_path.glob("*"))

if not afspacker_unpack_path.is_dir():
    afspacker_unpack_path.mkdir()
    # AFSPacker.exe unpack afss_path in afspacker_unpack_path 
    for afs_path in afss_paths:
        afspacker_extract(afs_path, afspacker_unpack_path / afs_path.stem)

# unpack afss_path unpack_path
for afs_path in afss_paths:
    afstool_unpack(afs_path, unpack_path / afs_path.stem)

# compare unpack_path afspacker_unpack_path
# AFSPacker don't store the date present in the filename directory in the file metadatas and update every dates when packing
for folder_path in unpack_path.glob("*"):
    compare_folders(folder_path / "root", afspacker_unpack_path / folder_path.stem)

print("###############################################################################")
print(f"# TEST 2/{TEST_COUNT}")
print("# Testing --stats command with all AFS and all unpacked AFS.")
print("###############################################################################")
for afs_path in afss_path.glob("*"):
    afstool_stats(afs_path)

for folder_path in unpack_path.glob("*"):
    afstool_stats(folder_path)

print("###############################################################################")
print(f"# TEST 3/{TEST_COUNT}")
print("# Comparing unpack_path->pack->[repack_path] AFS with [afss_path].")
print("###############################################################################")
repack_path.mkdir()
# repack unpack_path repack_path
for folder_path in unpack_path.glob("*"):
    afstool_pack(folder_path, repack_path / Path(folder_path.stem).with_suffix('.afs'))

# compare afss_path repack_path
compare_folders(afss_path, repack_path)

shutil.rmtree(repack_path)

print("###############################################################################")
print(f"# TEST 4/{TEST_COUNT}")
print("# Comparing [unpack_path]->patch->pack->unpack->[unpack2_path].")
print("###############################################################################")
# Patch unpack files whithout changing their len
for folder_path in unpack_path.glob("*"):
    print(f"Patching {folder_path}...")
    for file_path in folder_path.glob("root/*"):
        patch_all_bytes(file_path)

repack_unpack2_compare()

print("###############################################################################")
print(f"# TEST 5/{TEST_COUNT}")
print("# Comparing [unpack_path]->patch(max_size)->pack->unpack->[unpack2_path].")
print("###############################################################################")
# Patch unpack files changing len to max
patch_unpackedfiles_in_folder(unpack_path)

repack_unpack2_compare()

print("###############################################################################")
print(f"# TEST 6/{TEST_COUNT}")
print("# Testing exception unpack_path->patch(max_size+1)->[pack]->repack_path.")
print("###############################################################################")
# Patch unpack files with 1 byte in a new used block in the first file
patch_unpackedfiles_in_folder(unpack_path, True)

repack_path.mkdir()

# repack unpack_path repack_path
for folder_path in unpack_path.glob("*"):
    try:
        afs = afstool.Afs()
        afs.pack(folder_path, repack_path / Path(folder_path.stem).with_suffix('.afs'))
        raise Exception(f"Error - Invalid file len check. Must raise an exception.")
    except afstool.AfsInvalidFileLenError:
        print(f"Correct AfsInvalidFileLenError - {folder_path}")

shutil.rmtree(repack_path)

print("###############################################################################")
print(f"# TEST 7/{TEST_COUNT}")
print("# Comparing [unpack_path]->patch(blocks - 1)->pack->unpack->[unpack2_path].")
print("###############################################################################")
# Patch unpack files with 1 block less
for folder_path in unpack_path.glob("*"):
    print(f"Patching {folder_path}...")
    for file_path in folder_path.glob("root/*"):
        patch_all_bytes(file_path, file_path.stat().st_size - afstool.Afs.ALIGN)

repack_unpack2_compare()
shutil.rmtree(unpack_path)

print("###############################################################################")
print(f"# TEST 8/{TEST_COUNT}")
print("# Comparing [afss_path]->unpack->rebuild->pack->[repack_path].")
print("###############################################################################")
unpack_path.mkdir()
repack_path.mkdir()

# unpack afss_path unpack_path
for afs_path in afss_path.glob("*"):
    afstool_unpack(afs_path, unpack_path / afs_path.stem)

# rebuild unpack_path
for folder_path in unpack_path.glob("*"):
    afstool_rebuild(folder_path)

config = ConfigParser()
# pack unpack_path repack_path
for folder_path in unpack_path.glob("*"):
    config.read(folder_path / "sys" / "afs_rebuild.conf")
    if config["Default"]["filename_directory"] == "True":
        if config["FilenameDirectory"]["fd_last_attribute_type"] == "unknown":
            continue
    afstool_pack(folder_path, repack_path / Path(folder_path.stem).with_suffix(".afs"))

# compare afss_path repack_path when fd_last_attribute_type != unknown
for file_path in repack_path.glob("*"):
    afs_path = afss_path / file_path.name
    if not compare_files(file_path, afs_path):
        raise Exception(f"Error - \"{file_path}\" and \"{afs_path}\" are different.")

shutil.rmtree(repack_path)
shutil.rmtree(unpack_path)

print("###############################################################################")
print(f"# TEST 9/{TEST_COUNT}")
print("# Testing exceptions - (afs_rebuild.conf & afs_rebuild.csv).")
print("###############################################################################")
unpack_path.mkdir()
repack_path.mkdir()

# Here we have to test by limits rebuild command with every params
afs_rebuild_conf1 = {
    "Default": {
        "AFS_MAGIC": "0x41465300",
        "files_rebuild_strategy": "auto",
        "filename_directory": "False",
    }
}
afs_rebuild_conf2 = {
    "Default": {
        "AFS_MAGIC": "0x41465300",
        "files_rebuild_strategy": "auto",
        "filename_directory": "True",
    },
    "FilenameDirectory": {
        "toc_offset_of_fd_offset": "auto",
        "fd_offset": "auto",
        "fd_last_attribute_type": "unknown"
    }
}

i = -1

afs_rebuild_conf1["Default"]["filename_directory"] = "abcd"
test_except(afs_rebuild_conf1, afstool.AfsFilenameDirectoryValueError, "b.bin/0x1/0x1000/b.bin")
afs_rebuild_conf1["Default"]["filename_directory"] = "False"

for afs_rebuild_conf in [afs_rebuild_conf1, afs_rebuild_conf2]:
    afs_rebuild_conf["Default"]["AFS_MAGIC"] = "1234"
    test_except(afs_rebuild_conf, afstool.AfsInvalidMagicNumberError)
    afs_rebuild_conf["Default"]["AFS_MAGIC"] = "0x41465300";

    afs_rebuild_conf["Default"]["files_rebuild_strategy"] = "abcd"
    test_except(afs_rebuild_conf, afstool.AfsInvalidFilesRebuildStrategy)
    afs_rebuild_conf["Default"]["files_rebuild_strategy"] = "auto"

    test_except(afs_rebuild_conf, afstool.AfsInvalidFilePathError, "d.bin/0x1/0x1000/d.bin")
    test_except(afs_rebuild_conf, afstool.AfsInvalidFieldsCountError, "b.bin/0x1/0x1000/b.bin/d")
    for tmp_conf in ["index", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf
        test_except(afs_rebuild_conf, afstool.AfsIndexValueError, "b.bin/123/0x1000/b.bin")
        test_except(afs_rebuild_conf, afstool.AfsIndexOverflowError, "b.bin/0x3/0x1000/b.bin")
        test_except(afs_rebuild_conf, afstool.AfsIndexCollisionError, "b.bin/0x1/0x1000/b.bin\nc.bin/0x1/0x2000/c.bin")

    for tmp_conf in ["offset", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf
        test_except(afs_rebuild_conf, afstool.AfsOffsetValueError, "b.bin/0x1/123/b.bin")
        test_except(afs_rebuild_conf, afstool.AfsOffsetAlignError, "b.bin/0x1/0x555/b.bin")
        test_except(afs_rebuild_conf, afstool.AfsOffsetCollisionError, "b.bin/0x1/0x8000/b.bin\nc.bin/0x2/0x8000/c.bin")

    for tmp_conf in ["auto", "index", "offset", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf
        test_except(afs_rebuild_conf, afstool.AfsEmptyBlockValueError, "123/0x800")
        test_except(afs_rebuild_conf, afstool.AfsEmptyBlockValueError, "0x800/123")
        test_except(afs_rebuild_conf, afstool.AfsEmptyBlockAlignError, "0x800/0x7ff")
        test_except(afs_rebuild_conf, afstool.AfsEmptyBlockAlignError, "0x7ff/0x800")

afs_rebuild_conf1["Default"]["files_rebuild_strategy"] = "auto"
afs_rebuild_conf2["Default"]["files_rebuild_strategy"] = "auto"
afs_rebuild_conf = afs_rebuild_conf2

afs_rebuild_conf["FilenameDirectory"]["toc_offset_of_fd_offset"] = "abcd"
test_except(afs_rebuild_conf, afstool.AfsFdOffsetOffsetValueError)
afs_rebuild_conf["FilenameDirectory"]["toc_offset_of_fd_offset"] = "auto"

afs_rebuild_conf["FilenameDirectory"]["fd_offset"] = "abcd"
test_except(afs_rebuild_conf, afstool.AfsFdOffsetValueError)
afs_rebuild_conf["FilenameDirectory"]["fd_offset"] = "auto"

afs_rebuild_conf["FilenameDirectory"]["fd_last_attribute_type"] = "abcd"
test_except(afs_rebuild_conf, afstool.AfsFdLastAttributeTypeValueError)
afs_rebuild_conf["FilenameDirectory"]["fd_last_attribute_type"] = "unknown"

afs_rebuild_conf["FilenameDirectory"]["fd_offset"] = "0x1000"
test_except(afs_rebuild_conf, afstool.AfsFdOffsetCollisionError, "a.bin/auto/0x1000/a.bin")
afs_rebuild_conf["FilenameDirectory"]["fd_offset"] = "auto"

print("###############################################################################")
print(f"# TEST 10/{TEST_COUNT}")
print("# Testing rebuild - (afs_rebuild.conf & afs_rebuild.csv).")
print("###############################################################################")
tmp_count = 10
raw_data = tmp_count * [None]
raw_header_data = tmp_count * [None]
raw_fd_header = tmp_count * [None]
raw_files_data = tmp_count * [None]
raw_fd_data = tmp_count * [None]

# toc: 00000000
raw_header_data[0] = b"\x41\x46\x53\x20"+list_bytes([0x1, 0x800, 0x800])
raw_fd_header[0]   = list_bytes([0x1000, 0x30])
raw_files_data[0]  = b"\xff"*0x800
raw_fd_data[0]     = b"00000000".ljust(0x30, b"\x00")
# toc: 00000000
raw_header_data[1] = b"\x41\x46\x53\x00"+list_bytes([0x1, 0x800, 0x800])
raw_fd_header[1]   = raw_fd_header[0]
raw_files_data[1]  = raw_files_data[0]
raw_fd_data[1]     = raw_fd_data[0]
# toc: bac content: bac
raw_header_data[2] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x800, 0x600, 0x1000, 0x500, 0x1800, 0x700])
raw_fd_header[2]   = list_bytes([0x2000, 0x90])
raw_files_data[2]  = (b"\xff"*0x600).ljust(0x800, b"\x00") + (b"\xff"*0x500).ljust(0x800, b"\x00") + (b"\xff"*0x700).ljust(0x800, b"\x00")
raw_fd_data[2]     = b"b.bin".ljust(0x30, b"\x00")+b"a.bin".ljust(0x30, b"\x00")+b"c.bin".ljust(0x30, b"\x00")
# toc: abc content: acb
raw_header_data[3] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x800, 0x500, 0x8000, 0x600, 0x1000, 0x700])
raw_fd_header[3]   = list_bytes([0x8800, 0x90])
raw_files_data[3]  = ((b"\xff"*0x500).ljust(0x800, b"\x00") + b"\xff"*0x700).ljust(0x7800, b"\x00") + (b"\xff"*0x600).ljust(0x800, b"\x00")
raw_fd_data[3]     = b"a.bin".ljust(0x30, b"\x00")+b"b.bin".ljust(0x30, b"\x00")+b"c.bin".ljust(0x30, b"\x00")
# toc: abc content: cba - free(0x800-0x1000) b->0x1000 a-len=0x1000
raw_header_data[4] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x1800, 0x900, 0x1000, 0x600, 0x800, 0x700])
raw_fd_header[4]   = list_bytes([0x2800, 0x90])
raw_files_data[4]  = (b"\xff"*0x700).ljust(0x800, b"\x00") + (b"\xff"*0x600).ljust(0x800, b"\x00") + (b"\xff"*0x900).ljust(0x1000, b"\x00")
raw_fd_data[4]     = raw_fd_data[3]
# a=auto/3000 b=2000/500 c=auto/1000 d=auto/2000
# toc: abcd content: cdba
raw_header_data[5] = b"\x41\x46\x53\x00"+list_bytes([0x4, 0x4800, 0x2901, 0x2800, 0x1902, 0x800, 0x903, 0x1800, 0x904])
raw_fd_header[5]   = list_bytes([0x7800, 0xc0])
raw_files_data[5]  = (b"\xff"*0x903).ljust(0x1000, b"\x00") + (b"\xff"*0x904).ljust(0x1000, b"\x00") + (b"\xff"*0x1902).ljust(0x2000, b"\x00") + (b"\xff"*0x2901).ljust(0x3000, b"\x00")
raw_fd_data[5]     = b"a.bin".ljust(0x30, b"\x00")+b"b.bin".ljust(0x30, b"\x00")+b"c.bin".ljust(0x30, b"\x00")+b"d.bin".ljust(0x30, b"\x00")
# toc: bac content: acb
raw_header_data[6] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x8000, 0x600, 0x800, 0x500, 0x1000, 0x700])
raw_fd_header[6]   = list_bytes([0x8800, 0x90])
raw_files_data[6]  = ((b"\xff"*0x500).ljust(0x800, b"\x00") + b"\xff"*0x700).ljust(0x7800, b"\x00") + (b"\xff"*0x600).ljust(0x800, b"\x00")
raw_fd_data[6]     = raw_fd_data[2]
# test mixed with (c-0-off=0x3800;b-1-l=0x2000;a-2-l=0x1000)
# toc: cba - content:bac sort filename then index : abc cba then allocate offset: b=800&len=2000 a=2800
raw_header_data[7] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x3800, 0x700, 0x800, 0x1901, 0x2800, 0x902])
raw_fd_header[7]   = list_bytes([0x4000, 0x90])
raw_files_data[7]  = (b"\xff"*0x1901).ljust(0x2000, b"\x00") + (b"\xff"*0x902).ljust(0x1000, b"\x00") + (b"\xff"*0x700).ljust(0x800, b"\x00")
raw_fd_data[7]     = b"c.bin".ljust(0x30, b"\x00")+b"b.bin".ljust(0x30, b"\x00")+b"a.bin".ljust(0x30, b"\x00")
# toc: bac - content: abc
raw_header_data[8] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x1000, 0x601, 0x800, 0x702, 0x1800, 0x500])
raw_fd_header[8]   = list_bytes([0x2000, 0x90])
raw_files_data[8]  = (b"\xff"*0x702).ljust(0x800, b"\x00") + (b"\xff"*0x601).ljust(0x800, b"\x00") + (b"\xff"*0x500).ljust(0x800, b"\x00")
raw_fd_data[8]     = raw_fd_data[2]
# toc: abc - content: abc empty_blocks : 0x800 -> 0x2800 a 0x3000 -> 0x6000 b 0x7000 -> 0x8800 c
raw_header_data[9] = b"\x41\x46\x53\x00"+list_bytes([0x3, 0x2800, 0x601, 0x6000, 0x702, 0x8800, 0x803])
raw_fd_header[9]   = list_bytes([0x9800, 0x90])
raw_files_data[9]  = b"\x00"*0x2000+(b"\xff"*0x601).ljust(0x800, b"\x00") + b"\x00"*0x3000 + (b"\xff"*0x702).ljust(0x800, b"\x00") + b"\x00"*0x2000 + (b"\xff"*0x803).ljust(0x1000, b"\x00")
raw_fd_data[9]     = raw_fd_data[3]

afs_rebuild_conf3 = copy.deepcopy(afs_rebuild_conf2)
afs_rebuild_conf3["FilenameDirectory"]["toc_offset_of_fd_offset"] = "0x500"
afs_rebuild_conf4 = copy.deepcopy(afs_rebuild_conf2)
afs_rebuild_conf4["FilenameDirectory"]["toc_offset_of_fd_offset"] = "0x7f8"

for afs_rebuild_conf in [afs_rebuild_conf1, afs_rebuild_conf2, afs_rebuild_conf3, afs_rebuild_conf4]:
    for j in range(len(raw_data)):
        raw_data[j] = raw_header_data[j]
        if afs_rebuild_conf["Default"]["filename_directory"] == "True":
            pad_len = int(afs_rebuild_conf["FilenameDirectory"]["toc_offset_of_fd_offset"][2:], 16) if afs_rebuild_conf["FilenameDirectory"]["toc_offset_of_fd_offset"] != "auto" else 0
            raw_data[j] = raw_data[j].ljust(pad_len, b"\x00")+raw_fd_header[j]
        raw_data[j] = (raw_data[j]).ljust(0x800, b"\x00") + raw_files_data[j]
    
    afs_rebuild_conf["Default"]["AFS_MAGIC"] = "0x41465320"
    test_rebuild_repack(afs_rebuild_conf, [("00000000", 0x800)], raw_data[0], raw_fd_data=raw_fd_data[0])
    afs_rebuild_conf["Default"]["AFS_MAGIC"] = "0x41465300"
    test_rebuild_repack(afs_rebuild_conf, [("00000000", 0x800)], raw_data[1], raw_fd_data=raw_fd_data[1])

    for tmp_conf in ["index", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf
        test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x500),("b.bin", 0x600),("c.bin", 0x700)], raw_data[2], "b.bin/0x0/auto/b.bin", raw_fd_data=raw_fd_data[2])
    for tmp_conf in ["offset", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf # sort files by offset
        test_rebuild_repack(afs_rebuild_conf, [("a.bin",  0x500),("b.bin",  0x600),("c.bin", 0x700)], raw_data[3], "b.bin/auto/0x8000/b.bin", raw_fd_data=raw_fd_data[3])
        test_rebuild_repack(afs_rebuild_conf, [("a.bin",  0x900),("b.bin",  0x600),("c.bin", 0x700)], raw_data[4], "b.bin/auto/0x1000/b.bin", raw_fd_data=raw_fd_data[4])
        test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x2901),("b.bin", 0x1902),("c.bin", 0x903),("d.bin", 0x904)], raw_data[5], "a.bin/auto/auto/a.bin\nb.bin/auto/0x2800/b.bin\nc.bin/auto/auto/c.bin\nd.bin/auto/auto/d.bin", raw_fd_data=raw_fd_data[5])

    afs_rebuild_conf["Default"]["files_rebuild_strategy"] = "mixed"
    test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x500),("b.bin",  0x600),("c.bin", 0x700)], raw_data[6], "b.bin/0x0/0x8000/b.bin", raw_fd_data=raw_fd_data[6])
    test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x902),("b.bin", 0x1901),("c.bin", 0x700)], raw_data[7], "c.bin/0x0/0x3800/c.bin\nb.bin/0x1/auto/b.bin\na.bin/0x2/auto/a.bin", raw_fd_data=raw_fd_data[7])
    test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x702),("b.bin",  0x601),("c.bin", 0x500)], raw_data[8], "c.bin/auto/0x1800/c.bin\nb.bin/auto/0x1000/b.bin\na.bin/0x1/0x800/a.bin", raw_fd_data=raw_fd_data[8])

    for tmp_conf in ["auto", "index", "offset", "mixed"]:
        afs_rebuild_conf["Default"]["files_rebuild_strategy"] = tmp_conf
        test_rebuild_repack(afs_rebuild_conf, [("a.bin", 0x601),("b.bin",  0x702),("c.bin", 0x803)], raw_data[9], "0x800/0x2000\n0x3000/0x3000\n0x7000/0x1800", raw_fd_data=raw_fd_data[9])

print("###############################################################################")
print("# Cleaning test folders.")
print("###############################################################################")
# Remove tests folders
shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
