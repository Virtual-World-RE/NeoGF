#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
from time import time


__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk, CrystalPixel"
__license__ = "MIT"
__status__ = "developpement"


afs_path            = Path("../z_all_unpacked/afs_usa/root")
mots_path            = Path("mot")

# Created tmp paths
unpack_path         = Path("unpack")
unpack2_path        = Path("unpack2")
repack_path         = Path("repack")


def compare_files(file1_path:Path, file2_path:Path):
    "Compare two files."
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


def compare_folders(folder1: Path, folder2: Path, compare_mtime:bool = False):
    """
    compare two folder
        -> raise an exception if there is a difference in paths or in file content
    """
    folder1_tmp_paths = list(folder1.glob("**/*"))
    folder1_file_count = len(folder1_tmp_paths)
    print(f"compare \"{folder1}\" - \"{folder2}\" ({folder1_file_count} files)")
    if folder1_file_count == 0:
        raise Exception(f"Error - Empty folder: {folder1}")

    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names in filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in folder1_tmp_paths]
    folder2_paths = [Path(*path.parts[len2:]) for path in folder2.glob("**/*")]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Error - Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")
    # 2. Compare files content
    for path1 in folder1_tmp_paths:
        if path1.is_file():
            path2 = folder2 / Path(*path1.parts[len1:])
            if path1.read_bytes() != path2.read_bytes():
                raise Exception(f"Error - \"{path1}\" and \"{path2}\" are different.")


##################################################
# gcmtool.py commands wrappers
##################################################
def mottool_unpack(mot_path:Path, folder_path:Path):
    if os.system(f"python mottool.py -u \"{mot_path}\" \"{folder_path}\"") != 0:
        raise Exception("Error while unpacking MOT file.")
def mottool_pack(folder_path:Path, mot_path:Path):
    if os.system(f"python mottool.py -p \"{folder_path}\" \"{mot_path}\"") != 0:
        raise Exception("Error while packing MOT folder.")


TEST_COUNT = 1


start = time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or unpack2_path.is_dir() or repack_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{unpack2_path}\n-{repack_path}")

if not mots_path.is_dir():
    mots_path.mkdir()
    for mot_path in afs_path.glob("*mot.bin"):
        shutil.copy(mot_path, mots_path / mot_path.name)

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Comparing [mots_path]->unpack->[repack]")
print("###############################################################################")
# unpack ROM in unpack_path
unpack_path.mkdir(parents=True)
repack_path.mkdir(parents=True)
for mot_path in mots_path.glob("*"):
    mottool_unpack(mot_path, unpack_path / mot_path.name)

for folder_path in unpack_path.glob("*"):
    mottool_pack(folder_path, (repack_path / folder_path.name).with_suffix(".bin"))

compare_folders(mots_path, repack_path)

print("Correct unpack repack.")

print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
# Remove tests folders
shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
