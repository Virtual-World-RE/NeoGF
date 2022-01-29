#!/usr/bin/env python3
from afstool import AfsInvalidFileLenError, Afs, FilenameResolver
import os
from pathlib import Path
import shutil
from time import time

__version__ = "0.0.5"
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
class AfsTest(Afs):
    # return a list of tuples with (offset, resolved filename)
    def get_range(self, folder_path:Path):
        sys_path = folder_path / "sys"
        self._Afs__loadsys_from_folder(sys_path)
        resolver = FilenameResolver(sys_path)

        offsets_names_map = [(0, "SYS TOC")]
        for i in range(0, self._Afs__file_count):
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
def compare_folders(folder1: Path, folder2: Path, compare_mtime=False):
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
    if max_len == None:
        max_len = len(file_data)
    elif max_len < len(file_data):
        file_data = file_data[:max_len]
    for i in range(0, len(file_data)):
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
            for i in range(0, len(offsets_names_map)):
                if offsets_names_map[i][1] == file_path.name:
                    if i+1 < len(offsets_names_map):
                        max_len = offsets_names_map[i+1][0] - offsets_names_map[i][0]
                        if bool_len:
                            max_len += 1
                    # else there is no limit because last file
                    else:
                        max_len = file_path.stat().st_size + Afs.ALIGN
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


TEST_COUNT = 7

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

# compare repack_path afss_path
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
        afs = Afs()
        afs.pack(folder_path, repack_path / Path(folder_path.stem).with_suffix('.afs'))
        raise Exception(f"Error - Invalid file len check. Must raise an exception.")
    except AfsInvalidFileLenError:
        print(f"Correct AfsInvalidFileLenError - {folder_path}")

shutil.rmtree(repack_path)

print("###############################################################################")
print(f"# TEST 7/{TEST_COUNT}")
print("# Comparing [unpack_path]->patch(blocks - 1)->pack->unpack->[unpack2_path].")
print("###############################################################################")
# Patch unpack files with 1 block less
for file_path in unpack_path.glob("*/root/*"):
    patch_all_bytes(file_path, file_path.stat().st_size - Afs.ALIGN)

repack_unpack2_compare()

print("###############################################################################")
print("# Cleaning test folders.")
print("###############################################################################")
# Remove tests folders
shutil.rmtree(unpack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
