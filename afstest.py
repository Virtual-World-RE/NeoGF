#!/usr/bin/env python3
from pathlib import Path
import hashlib
import os
import shutil


__version__ = "0.0.2"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


##################################################
# Set afss_path with your AFSs folder
##################################################
afss_path    = Path("afs")
unpack_path  = Path("unpack")
unpack2_path = Path("unpack2")
repack_path  = Path("repack")
afspacker_unpack_path = Path("afspacker_unpack")
afspacker_path = Path("../_autres/_soft/AFSPacker.exe")


def print_paths_differences(folder1_paths:list, folder2_paths:list):
    backup_paths = folder2_paths.copy()
    for path in folder1_paths:
        if path in folder2_paths:
            folder2_paths.remove(path)
    for path in backup_paths:
        if path in folder1_paths:
            folder1_paths.remove(path)
    print("folder1 diff :")
    for path in folder1_paths:
        print(path)
    print("folder2 diff :")
    for path in folder2_paths:
        print(path)


# compare two files sha256
def compare_sha256(file1_path:Path, file2_path:Path):
    return hashlib.sha256( file1_path.read_bytes() ).hexdigest() == hashlib.sha256( file2_path.read_bytes() ).hexdigest()


# compare two AFS
#     -> raise an exception if there is a difference
def verify_AFS_sha256(folder1: Path, folder2: Path):
    print(f"compare \"{folder1}\" - \"{folder2}\"")
    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names of filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in (folder1/"root").glob('*')]
    folder2_paths = [Path(*path.parts[len2:]) for path in (folder2/"root").glob('*')]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")

    for path1 in (folder1).glob('*'):
        path2 = folder2/Path(*path1.parts[len1:])
        if not compare_sha256(path1, path2):
            raise Exception(f"\"{path1}/\" and \"{path2}\" are different.")


print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or unpack2_path.is_dir() or repack_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{unpack2_path}\n{repack_path}")

print("###############################################################################")
print("# Comparing unpacked AFS with AFSPacker unpacks.")
print("###############################################################################")
unpack_path.mkdir()
if not afspacker_unpack_path.is_dir():
    afspacker_unpack_path.mkdir()
    # AFSPacker.exe unpack afss_path in afspacker_unpack_path 
    for afs_path in afss_path.glob("*"):
        print(f"AFSPacker.exe : Extracting \"{afs_path}\" in \"{afspacker_unpack_path}/{afs_path.stem}\"")
        if os.system(f"{afspacker_path} -e \"{afs_path}\" \"{afspacker_unpack_path}/{afs_path.stem}\" > NUL") != 0:
            raise Exception("Error while unpacking with AFSPacker.exe")

# unpack afss_path unpack_path
for afs_path in afss_path.glob("*"):
    if os.system(f"python afstool.py -u \"{afs_path}\" \"{unpack_path}/{afs_path.stem}\"") != 0:
        raise Exception("Error while unpacking.")

# compare unpack_path afspacker_unpack_path
for folder_path in unpack_path.glob("*"):
    if folder_path.is_dir():
        verify_AFS_sha256(folder_path/"root", afspacker_unpack_path / folder_path.stem)

print("###############################################################################")
print("# Comparing repacked AFS with originals AFS.")
print("###############################################################################")
repack_path.mkdir()
# repack unpack_path repack_path
for folder_path in unpack_path.glob("*"):
    if os.system(f"python afstool.py -p \"{folder_path}\" \"{repack_path}/{Path(folder_path.stem).with_suffix('.afs')}\"") != 0:
        raise Exception("Error while repacking.")

# compare unpack_path afspacker_unpack_path
for afs_path in repack_path.glob("*"):
    print(f"compare \"{afs_path}\" - \"{afss_path / Path(folder_path.stem).with_suffix('.afs')}\"")
    compare_sha256(afs_path, afss_path / Path(folder_path.stem).with_suffix(".afs"))

# Patch unpack files whithout changing their len
# Patch unpack files changing len to max
# Patch unpack files with 1 byte in a new block
# Patch unpack files with 1 block less




print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")

# Remove tests folders
if unpack_path.is_dir():
    shutil.rmtree(unpack_path)
if unpack2_path.is_dir():
    shutil.rmtree(unpack2_path)
if repack_path.is_dir():
    shutil.rmtree(repack_path)

print("###############################################################################")
print("# All tests are OK")
print("###############################################################################")
