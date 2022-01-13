#!/usr/bin/env python3
from pathlib import Path
import hashlib
import os
import shutil


__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"
##################################################
# Set roms_path with your ROMs (at the root of the ROM folder)
# Extract all files from file system using dolphin emu - put it in dolphin_extracts/root/
# Extract boot.dol and apploader.img using dolphin emu - put it in dolphin_extracts/sys/
##################################################
roms_path       = Path("../ROM")
unpack_path     = Path("tests/unpack")
repack_iso_path = Path("tests/repack_iso")
unpack2_path    = Path("tests/unpack2")
dolphin_path    = Path("tests/dolphin_extracts")
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
    with file1_path.open("rb") as f1, file2_path.open("rb") as f2:
        if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
            return False
    return True


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
        raise Exception(f"Folders \"{folder1}\" and \"{folder2}\" are differents (not the sames folders or files names).")
    # 2. Compare sys files content
    if not compare_sha256(folder1/"sys"/"apploader.img", folder2/"sys"/"apploader.img"):
        raise Exception(f"\"{folder1}/sys/apploader.bin\" and \"{folder2}/sys/apploader.bin\" are differents.")
    if not compare_sha256(folder1/"sys"/"boot.dol", folder2/"sys"/"boot.dol"):
        raise Exception(f"\"{folder1}/sys/boot.bin\" and \"{folder2}/sys/boot.bin\" are differents.")

    for path1 in (folder1/"root").glob('**/*'):
        if path1.is_file():
            path2 = folder2/Path(*path1.parts[len1:])
            if not compare_sha256(path1, path2):
                raise Exception(f"\"{path1}/\" and \"{path2}\" are differents.")


print("# Cleaning tests folder")
# Remove tests folders
if unpack_path.is_dir():
    shutil.rmtree(unpack_path)
if repack_iso_path.is_dir():
    shutil.rmtree(repack_iso_path)
if unpack2_path.is_dir():
    shutil.rmtree(unpack2_path)

print("# Comparing unpacked ROMs with dolphin extracts")
# unpack ROM in unpack
unpack_path.mkdir(parents=True)
for iso_path in roms_path.glob("*"):
    if iso_path.is_file():
        if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack_path}/{iso_path.name}\"") != 0:
            raise Exception("Error")

# compare unpack dolphin_extracts
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, dolphin_path / folder_path.name)

print("# Comparing iso->[1:unpacked]->repacked->[2:unpacked]")
# repack unpack repack_iso
repack_iso_path.mkdir()
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -p \"{folder_path}\" \"{repack_iso_path}/{folder_path.name}\"") != 0:
        raise Exception("Error")

# unpack repack_iso unpack2
unpack2_path.mkdir()
for iso_path in repack_iso_path.glob("*"):
    if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack2_path}/{iso_path.name}\"") != 0:
        raise Exception("Error")

# remove repack_iso
shutil.rmtree(repack_iso_path)

# compare unpack unpack2
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, unpack2_path / folder_path.name)

# remove unpack2
shutil.rmtree(unpack2_path)

print("# Comparing iso->[1:unpacked]->rebuild_fst->repack->[2:unpacked]")
# rebuild unpack fst
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -r \"{folder_path}\"") != 0:
        raise Exception("Error")

# repack unpack repack_iso
repack_iso_path.mkdir()
for folder_path in unpack_path.glob("*"):
    if os.system(f"python gcmtool.py -p \"{folder_path}\" \"{repack_iso_path}/{folder_path.name}\"") != 0:
        raise Exception("Error")

# unpack repack_iso unpack2
unpack2_path.mkdir()
for iso_path in repack_iso_path.glob("*"):
    if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{unpack2_path}/{iso_path.name}\"") != 0:
        raise Exception("Error")

# remove repack_iso
shutil.rmtree(repack_iso_path)

# compare unpack unpack2
for folder_path in unpack_path.glob("*"):
    verify_GCM_sha256(folder_path, unpack2_path / folder_path.name)

# remove unpack unpack2
shutil.rmtree(unpack_path)
shutil.rmtree(unpack2_path)

print("# All tests are OK")
