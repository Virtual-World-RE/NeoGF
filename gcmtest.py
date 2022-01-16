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
# Set roms_path with your ROMs (at the root of the ROM folder)
# Extract all files from file system using dolphin emu - put it in gcm_dolphin/root/
# Extract boot.dol and apploader.img using dolphin emu - put it in gcm_dolphin/sys/
##################################################
roms_path           = Path("../ROM")
dolphin_unpack_path = Path("dolphin_unpack")
unpack_path         = Path("unpack")
repack_path         = Path("repack")
unpack2_path        = Path("unpack2")
# if there is a way to create symlinks on GCM filesystem, it could create strange situations


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


# compare two GCM
#     -> raise an exception if there is a difference
def verify_GCM_sha256(folder1: Path, folder2: Path):
    print(f"compare \"{folder1}\" - \"{folder2}\"")
    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names of filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in (folder1/"root").glob('**/*')]
    folder2_paths = [Path(*path.parts[len2:]) for path in (folder2/"root").glob('**/*')]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")
    # 2. Compare sys files content
    if not compare_sha256(folder1/"sys"/"apploader.img", folder2/"sys"/"apploader.img"):
        raise Exception(f"\"{folder1}/sys/apploader.bin\" and \"{folder2}/sys/apploader.bin\" are different.")
    if not compare_sha256(folder1/"sys"/"boot.dol", folder2/"sys"/"boot.dol"):
        raise Exception(f"\"{folder1}/sys/boot.bin\" and \"{folder2}/sys/boot.bin\" are different.")

    for path1 in (folder1/"root").glob('**/*'):
        if path1.is_file():
            path2 = folder2/Path(*path1.parts[len1:])
            if not compare_sha256(path1, path2):
                raise Exception(f"\"{path1}/\" and \"{path2}\" are different.")


print("# Cleaning tests folder")
# Remove tests folders
if unpack_path.is_dir():
    shutil.rmtree(unpack_path)
if repack_path.is_dir():
    shutil.rmtree(repack_path)
if unpack2_path.is_dir():
    shutil.rmtree(unpack2_path)
print("# Comparing unpacked ROMs with dolphin extracts")
# unpack ROM in unpack_path
unpack_path.mkdir(parents=True)
for iso_path in roms_path.glob("*"):
    if iso_path.is_file():
        if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack_path}/{iso_path.name}\"") != 0:
            raise Exception("Error while unpacking original gcm.")

# compare unpack_path dolphin_unpack_path
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, dolphin_unpack_path / folder_path.name)

print("# Comparing iso->[1:unpacked]->repacked->[2:unpacked]")
# repack unpack_path repack_path
repack_path.mkdir()
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -p \"{folder_path}\" \"{repack_path}/{folder_path.name}\"") != 0:
        raise Exception("Error while packing unpacked gcm.")

# unpack repack_path unpack2_path
unpack2_path.mkdir()
for iso_path in repack_path.glob("*"):
    if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack2_path}/{iso_path.name}\"") != 0:
        raise Exception("Error while unpacking repacked gcm.")

# remove repack_path
shutil.rmtree(repack_path)

# compare unpack_path unpack2_path
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, unpack2_path / folder_path.name)

# remove unpack2_path
shutil.rmtree(unpack2_path)

print("# Comparing iso->[1:unpacked]->rebuild_fst->repack->[2:unpacked]")
# rebuild unpack_path FSTs
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -r \"{folder_path}\"") != 0:
        raise Exception("Error while rebuilding FST.")

# repack unpack_path repack_path
repack_path.mkdir()
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -p \"{folder_path}\" \"{repack_path}/{folder_path.name}\"") != 0:
        raise Exception("Error while packing gcm with new FST.")

# unpack repack_path unpack2_path
unpack2_path.mkdir()
for iso_path in repack_path.glob("*"):
    if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack2_path}/{iso_path.name}\"") != 0:
        raise Exception("Error while unpacking repacked gcm with new FST.")

# remove repack_path
shutil.rmtree(repack_path)

# compare unpack_path unpack2_path
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, unpack2_path / folder_path.name)

# remove unpack_path unpack2_path
print(f"# Removing {unpack_path} and {unpack2_path}.")
shutil.rmtree(unpack_path)
shutil.rmtree(unpack2_path)

print("# All tests are OK")