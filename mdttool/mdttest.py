#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
from time import time


__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk, CrystalPixel"
__license__ = "MIT"
__status__ = "developpement"


mdts_path           = Path("mdt")

# Created tmp paths
unpack_path         = Path("unpack")
unpack2_path        = Path("unpack2")
repack_path         = Path("repack")


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


def compare_folders(folder1: Path, folder2: Path):
    """
    Compare two folders
        -> raise an exception if there is a difference
    """
    folder1_root_paths = list((folder1).glob("**/*"))
    folder1_file_count = len(folder1_root_paths)
    print(f"compare \"{folder1}\" - \"{folder2}\" ({folder1_file_count} files)")
    if folder1_file_count == 0:
        raise Exception(f"Error - Empty folder: {folder1}")

    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names of filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in folder1_root_paths]
    folder2_paths = [Path(*path.parts[len2:]) for path in (folder2).glob('**/*')]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Error - Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")
    # 2. Compare files content
    for path1 in folder1_root_paths:
        if path1.is_file():
            path2 = folder2/Path(*path1.parts[len1:])
            if not compare_files(path1, path2):
                raise Exception(f"Error - \"{path1}\" and \"{path2}\" are different.")


##################################################
# mdttool.py commands wrappers
##################################################
def mdttool_unpack(mdt_path:Path, folder_path:Path, charset:str):
    if os.system(f"python mdttool.py -u \"{mdt_path}\" \"{folder_path}\" -c {charset}") != 0:
        raise Exception("Error while unpacking MDT.")
def mdttool_pack(folder_path:Path, mdt_path:Path):
    if os.system(f"python mdttool.py -p \"{folder_path}\" \"{mdt_path}\"") != 0:
        raise Exception("Error while packing MDT.")


TEST_COUNT = 1


start = time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or unpack2_path.is_dir() or repack_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{unpack2_path}\n-{repack_path}")

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Comparing [mdts_path]->unpack->[repack]")
print("###############################################################################")
# unpack mdts in unpack_path
unpack_path.mkdir()
repack_path.mkdir()

for mdt_path in mdts_path.glob("**/*"):
    if mdt_path.is_file():
        (unpack_path / mdt_path.parent.name).mkdir(exist_ok=True)
        mdttool_unpack(mdt_path, unpack_path / mdt_path.parent.name / mdt_path.stem, mdt_path.parent.name)

unpacked_paths = []
for path in unpack_path.glob("**/*"):
    if path.is_file() and path.parent not in unpacked_paths:
        unpacked_paths.append(path.parent)

for folder_path in unpacked_paths:
    (repack_path / folder_path.parent.name).mkdir(exist_ok=True)
    mdttool_pack(folder_path, repack_path / folder_path.parent.name / (folder_path.name + ".mdt"))

# compare mdts_path repack_path
compare_folders(mdts_path, repack_path)

print("Correct unpack / repack.")

print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
# Remove tests folders
shutil.rmtree(repack_path)
shutil.rmtree(unpack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
