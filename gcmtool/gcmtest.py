#!/usr/bin/env python3
from pathlib import Path
import os
import shutil
from time import time
from gcmtool import Gcm
from gcmtool import InvalidDVDMagicError, InvalidUnpackFolderError, InvalidPackIsoError, InvalidFSTSizeError, DolSizeOverflowError, InvalidRootFileFolderCountError, InvalidFSTFileSizeError, FSTDirNotFoundError, FSTFileNotFoundError, BadAlignError


__version__ = "0.0.9"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


##################################################
# Set roms_path with your ROMs (at the root of the ROM folder)
# Extract all files from file system using dolphin emu - put it in f"{dolphin_unpack_path}/root/"
# Extract boot.dol and apploader.img using dolphin emu - put it in f"{dolphin_unpack_path}/sys/"
##################################################
roms_path           = Path("../ROM")
dolphin_unpack_path = Path("dolphin_unpack")

# Created tmp paths
unpack_path         = Path("unpack")
unpack2_path        = Path("unpack2")
repack_path         = Path("repack")
# if there is a way to create symlinks on GCM filesystem, it could create strange situations


def test_storage():
    total, used, free = shutil.disk_usage("/")
    if free - 10**10 < 3 * sum(path.stat().st_size for path in roms_path.glob('*') if path.is_file()):
        raise Exception("Error - Not enought free space on the disk to run tests.")


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


def compare_GCM(folder1: Path, folder2: Path):
    """
    Compare two GCM
        -> raise an exception if there is a difference
    """
    folder1_root_paths = list((folder1 / "root").glob("**/*"))
    folder1_file_count = len(folder1_root_paths)
    print(f"compare \"{folder1}\" - \"{folder2}\" ({folder1_file_count} files)")
    if folder1_file_count == 0:
        raise Exception(f"Error - Empty folder: {folder1}")

    len1 = len(folder1.parts)
    len2 = len(folder2.parts)
    # 1. Compare names of filesystems
    folder1_paths = [Path(*path.parts[len1:]) for path in folder1_root_paths]
    folder2_paths = [Path(*path.parts[len2:]) for path in (folder2 / "root").glob('**/*')]
    if folder1_paths != folder2_paths:
        print_paths_differences(folder1_paths, folder2_paths)
        raise Exception(f"Error - Folders \"{folder1}\" and \"{folder2}\" are different (not the same folders or files names).")
    # 2. Compare sys files content
    if not compare_files(folder1 / "sys" / "apploader.img", folder2 / "sys" / "apploader.img"):
        raise Exception(f"Error - \"{folder1 / 'sys/apploader.bin'}\" and \"{folder2 / 'sys/apploader.bin'}\" are different.")
    if not compare_files(folder1 / "sys" / "boot.dol", folder2 / "sys" / "boot.dol"):
        raise Exception(f"Error - \"{folder1 / 'sys/boot.bin'}\" and \"{folder2 / 'sys/boot.bin'}\" are different.")

    for path1 in folder1_root_paths:
        if path1.is_file():
            path2 = folder2/Path(*path1.parts[len1:])
            if not compare_files(path1, path2):
                raise Exception(f"Error - \"{path1}\" and \"{path2}\" are different.")


##################################################
# gcmtool.py commands wrappers
##################################################
def gcmtool_unpack(iso_path:Path, folder_path:Path):
    if os.system(f"python gcmtool.py -u \"{iso_path}\" \"{folder_path}\"") != 0:
        raise Exception("Error while unpacking GCM.")
def gcmtool_pack(folder_path:Path, iso_path:Path, disable_ignore:bool = False):
    if os.system(f"python gcmtool.py -p {'-di' if disable_ignore else ''} \"{folder_path}\" \"{iso_path}\"") != 0:
        raise Exception("Error while packing GCM.")
def gcmtool_rebuild_fst(folder_path:Path):
    if os.system(f"python gcmtool.py -r \"{folder_path}\"") != 0:
        raise Exception("Error while rebuilding FST.")
def gcmtool_stats(path:Path):
    if os.system(f"python gcmtool.py -s \"{path}\" > NUL") != 0:
        raise Exception("Error while getting stats.")


TEST_COUNT = 5

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
print("# Comparing roms_path->unpack->[unpack_path] ROMs with [dolphin_unpack_path]")
print("###############################################################################")
# unpack ROM in unpack_path
unpack_path.mkdir(parents=True)
for iso_path in roms_path.glob("*"):
    if iso_path.is_file():
        gcmtool_unpack(iso_path, unpack_path / iso_path.name)

# compare unpack_path dolphin_unpack_path
for folder_path in unpack_path.glob("*"):
    compare_GCM(folder_path, dolphin_unpack_path / folder_path.name)

print("###############################################################################")
print(f"# TEST 2/{TEST_COUNT}")
print("# Testing stats on folders & isos")
print("###############################################################################")
for iso_path in roms_path.glob("*"):
    if iso_path.is_file():
        gcmtool_stats(iso_path)

for folder_path in unpack_path.glob("*"):
    gcmtool_stats(folder_path)

print("###############################################################################")
print(f"# TEST 3/{TEST_COUNT}")
print("# Comparing [unpack_path]->pack->unpack->[unpack2_path]")
print("###############################################################################")
# repack unpack_path repack_path
repack_path.mkdir()
unpack_paths = list(unpack_path.glob("*"))
for folder_path in unpack_paths:
    gcmtool_pack(folder_path, repack_path / folder_path.name, disable_ignore = folder_path.name == "Metroid Prime (USA).iso")

# unpack repack_path unpack2_path
unpack2_path.mkdir()
for iso_path in repack_path.glob("*"):
    gcmtool_unpack(iso_path, unpack2_path / iso_path.name)

# remove repack_path
shutil.rmtree(repack_path)

# compare unpack_path unpack2_path
for folder_path in unpack_paths:
    compare_GCM(folder_path, unpack2_path / folder_path.name)

# remove unpack2_path
shutil.rmtree(unpack2_path)

print("###############################################################################")
print(f"# TEST 4/{TEST_COUNT}")
print("# Comparing [unpack_path]->rebuild_fst->repack->unpack->[unpack2_path]")
print("###############################################################################")
# rebuild unpack_path FSTs
unpack_paths = list(unpack_path.glob("*"))
for folder_path in unpack_paths:
    gcmtool_rebuild_fst(folder_path)

# repack unpack_path repack_path
repack_path.mkdir()
for folder_path in unpack_paths:
    gcmtool_pack(folder_path, repack_path / folder_path.name, disable_ignore = folder_path.name == "Metroid Prime (USA).iso")

# unpack repack_path unpack2_path
unpack2_path.mkdir()
for iso_path in repack_path.glob("*"):
    gcmtool_unpack(iso_path, unpack2_path / iso_path.name)

# compare unpack_path unpack2_path
for folder_path in unpack_path.glob("*"):
    compare_GCM(folder_path, unpack2_path / folder_path.name)

# remove unpack2_path
shutil.rmtree(unpack_path)
shutil.rmtree(unpack2_path)

print("###############################################################################")
print(f"# TEST 5/{TEST_COUNT}")
print("# Testing exceptions.")
print("###############################################################################")
gcm = Gcm()
first_repacked = list(repack_path.glob("*"))[0]
# change DVD magic
with first_repacked.open("rb+") as first_repacked_file:
    first_repacked_file.seek(0x1c)
    first_repacked_file.write(b"\xC2\x33\x9F\x3E")

try:
    gcm.unpack(first_repacked, unpack2_path / first_repacked.name)
    raise Exception("Error - InvalidDVDMagicError should have been triggered.")
except InvalidDVDMagicError:
    print("Correct InvalidDVDMagicError triggered.")

# restore DVD magic
with first_repacked.open("rb+") as first_repacked_file:
    first_repacked_file.seek(0x1c)
    first_repacked_file.write(b"\xC2\x33\x9F\x3D")

(unpack2_path / first_repacked.stem).mkdir(parents=True)
try:
    gcm.unpack(first_repacked, unpack2_path / first_repacked.stem)
    raise Exception("Error - InvalidUnpackFolderError should have been triggered.")
except InvalidUnpackFolderError:
    print("Correct InvalidUnpackFolderError triggered.")

shutil.rmtree(unpack2_path)

unpack_path.mkdir()
first_unpacked = unpack_path / "Final Fantasy - Crystal Chronicles (Europe) (En,Fr,De,Es,It).iso"
gcmtool_unpack(roms_path / first_unpacked.name, first_unpacked)
try:
    gcm.pack(first_unpacked, first_repacked)
    raise Exception("Error - InvalidPackIsoError should have been triggered.")
except InvalidPackIsoError:
    print("Correct InvalidPackIsoError triggered.")

fst_data = (first_unpacked / "sys/fst.bin").read_bytes()
(first_unpacked / "sys/fst.bin").write_bytes(fst_data + b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - InvalidFSTSizeError should have been triggered.")
except InvalidFSTSizeError:
    print("Correct InvalidFSTSizeError triggered.")
(first_unpacked / "sys/fst.bin").write_bytes(fst_data)

(first_unpacked / "root/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa").mkdir()
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - InvalidRootFileFolderCountError should have been triggered.")
except InvalidRootFileFolderCountError:
    print("Correct InvalidRootFileFolderCountError triggered.")
(first_unpacked / "root/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa").rmdir()

first_unpacked_file = None
first_unpacked_dir = None
for path in (first_unpacked / "root").glob("*"):
    if path.is_file() and first_unpacked_file is None:
        first_unpacked_file = path
    elif path.is_dir() and first_unpacked_dir is None:
        first_unpacked_dir = path
    if first_unpacked_file is not None and first_unpacked_dir is not None:
        break

first_unpacked_file_data = first_unpacked_file.read_bytes()
first_unpacked_file.write_bytes(first_unpacked_file_data + b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - InvalidFSTFileSizeError should have been triggered.")
except InvalidFSTFileSizeError:
    print("Correct InvalidFSTFileSizeError triggered.")
first_unpacked_file.write_bytes(first_unpacked_file_data)

new_dir = first_unpacked_dir.rename(first_unpacked_dir.parent / (first_unpacked_dir.name +"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - FSTDirNotFoundError should have been triggered.")
except FSTDirNotFoundError:
    print("Correct FSTDirNotFoundError triggered.")
new_dir.rename(first_unpacked_dir)

new_file = first_unpacked_file.rename(first_unpacked_file.parent / (first_unpacked_file.name +"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - FSTFileNotFoundError should have been triggered.")
except FSTFileNotFoundError:
    print("Correct FSTFileNotFoundError triggered.")
new_file.rename(first_unpacked_file)

#| 0001ec00 | 0023f9a0 | 00220da0 | boot.dol
#| 0023fa00 | 00276058 | 00036658 | fst.bin
# dol size for overflowing on FST + 1: 0023fa00 - 0001ec00 = 220e00
backup_dol_data = (first_unpacked / "sys/boot.dol").read_bytes()
with (first_unpacked / "sys/boot.dol").open("rb+") as bootdol_file:
    bootdol_file.seek(0x220e00)
    bootdol_file.write(b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - DolSizeOverflowError should have been triggered.")
except DolSizeOverflowError:
    print("Correct DolSizeOverflowError triggered.")
(first_unpacked / "sys/boot.dol").write_bytes(backup_dol_data)

with (first_unpacked / "sys/boot.dol").open("rb+") as bootdol_file:
    bootdol_file.seek(0x220dff)
    bootdol_file.write(b"\x00")
gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "ok1.iso"))
print("Correct pack with max dol size before FST.")

# patch boot.bin to put fst before dol and make dol overflow on first file
# fst_len = 00036658 and new offset 0001ec00
with (first_unpacked / "sys/boot.bin").open("rb+") as bootbin:
    bootbin.seek(0x420) # dol offset
    bootbin.write(b"\x00\x05\x53\x00") # after the FST
    # now seeked on FST offset
    bootbin.write(b"\x00\x01\xEC\x00") # replace the dol
#| 0001ec00 | 00055258 | 00036658 | fst.bin
#| 00055300 | ?        | ?        | boot.dol
#| 00278000 | 005111de | 002991de | game.MAP
# max dol size = 00278000 - 00055300 = 222D00
with (first_unpacked / "sys/boot.dol").open("rb+") as bootdol_file:
    bootdol_file.seek(0x222cff)
    bootdol_file.write(b"\x00")
gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "ok2.iso"))
print("Correct pack with max dol size before first file.")

with (first_unpacked / "sys/boot.dol").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x222d00)
    first_unpacked_file.write(b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - DolSizeOverflowError should have been triggered.")
except DolSizeOverflowError:
    print("Correct DolSizeOverflowError triggered.")

# Remove tests folders
print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
shutil.rmtree(repack_path)
shutil.rmtree(unpack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
