#!/usr/bin/env python3
from configparser import ConfigParser
from gcmtool import Gcm, align_top
from gcmtool import InvalidDVDMagicError, InvalidUnpackFolderError, InvalidPackIsoError, \
    InvalidFSTSizeError, DolSizeOverflowError, InvalidRootFileFolderCountError, \
    InvalidFSTFileSizeError, FSTDirNotFoundError, FSTFileNotFoundError, BadAlignError, \
    FstSizeOverflowError, InvalidConfValueError, ApploaderOverflowError
import os
from pathlib import Path
import shutil
from time import time


__version__ = "0.2.1"
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

(first_unpacked / ("root/" + "a"*36)).mkdir()
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - InvalidRootFileFolderCountError should have been triggered.")
except InvalidRootFileFolderCountError:
    print("Correct InvalidRootFileFolderCountError triggered.")
(first_unpacked / ("root/" + "a"*36)).rmdir()

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

new_dir = first_unpacked_dir.rename(first_unpacked_dir.parent / (first_unpacked_dir.name +"a"*36))
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - FSTDirNotFoundError should have been triggered.")
except FSTDirNotFoundError:
    print("Correct FSTDirNotFoundError triggered.")
new_dir.rename(first_unpacked_dir)

new_file = first_unpacked_file.rename(first_unpacked_file.parent / (first_unpacked_file.name +"a"*36))
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

with (first_unpacked / "sys/boot.dol").open("wb") as first_unpacked_file:
    first_unpacked_file.seek(0x222cff)
    first_unpacked_file.write(b"\x00")

# max fst_size = 55300 - 1ec00 = 36700
with (first_unpacked / "sys/fst.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x366ff)
    first_unpacked_file.write(b"\x00")
with (first_unpacked / "sys/boot.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x428)
    first_unpacked_file.write(b"\x00\x03\x67\x00") # FST len
    first_unpacked_file.write(b"\x00\x03\x67\x00") # FST max len
gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "ok3.iso"))
print("Correct pack with max FST size before dol.")

with (first_unpacked / "sys/fst.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x36700)
    first_unpacked_file.write(b"\x00")
with (first_unpacked / "sys/boot.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x428)
    first_unpacked_file.write(b"\x00\x03\x67\x01") # FST len
    first_unpacked_file.write(b"\x00\x03\x67\x01") # FST max len
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - FstSizeOverflowError should have been triggered.")
except FstSizeOverflowError:
    print("Correct FstSizeOverflowError triggered.")

#| 0001ec00 |   241900 |   222d00 | boot.dol
#| 00241900 | ?        | ?        | fst.bin
#| 00278000 | 005111de | 002991de | game.MAP
# fst max len = 278000 - 241900 = 36700
with (first_unpacked / "sys/boot.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x420)
    first_unpacked_file.write(b"\x00\x01\xec\x00") # dol offset
    first_unpacked_file.write(b"\x00\x24\x19\x00") # FST offset
    first_unpacked_file.write(b"\x00\x03\x67\x00") # FST len
    first_unpacked_file.write(b"\x00\x03\x67\x00") # FST max len
with (first_unpacked / "sys/fst.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x36700)
    first_unpacked_file.truncate()
gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "ok4.iso"))
print("Correct pack with max FST size before first file.")

with (first_unpacked / "sys/boot.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x428)
    first_unpacked_file.write(b"\x00\x03\x67\x01") # FST len
    first_unpacked_file.write(b"\x00\x03\x67\x01") # FST max len
with (first_unpacked / "sys/fst.bin").open("rb+") as first_unpacked_file:
    first_unpacked_file.seek(0x36700)
    first_unpacked_file.write(b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / (first_unpacked.stem + "except.iso"))
    raise Exception("Error - FstSizeOverflowError should have been triggered.")
except FstSizeOverflowError:
    print("Correct FstSizeOverflowError triggered.")

shutil.rmtree(repack_path)
shutil.rmtree(unpack_path)

print("###############################################################################")
print(f"# TEST 6/{TEST_COUNT}")
print("# Testing system.conf values.")
print("###############################################################################")
# unpack a ROM in unpack_path
unpack_path.mkdir(parents=True)
repack_path.mkdir(parents=True)
first_unpacked = None
for iso_path in roms_path.glob("*"):
    if iso_path.is_file():
        first_unpacked = unpack_path / iso_path.name
        gcmtool_unpack(iso_path, first_unpacked)

        delete_files = False
        for path in (first_unpacked / "root").glob("**/*"):
            if path.is_file():
                if not delete_files:
                    delete_files = True
                    continue
                path.unlink()
        gcmtool_rebuild_fst(first_unpacked)
        break

config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
config.optionxform = str # makes options case sensitive
config.read(first_unpacked / "sys/system.conf")
config["Default"]["boot.bin_section"] = "enabled"
config["Default"]["bi2.bin_section"] = "enabled"
config["Default"]["apploader.img_section"] = "enabled"

bootbin_expected_data = bytearray( (first_unpacked / "sys/boot.bin").read_bytes() )
bi2bin_expected_data = bytearray( (first_unpacked / "sys/bi2.bin").read_bytes() )
apploaderimg_expected_data = bytearray( (first_unpacked / "sys/apploader.img").read_bytes() )

def test_config_pack(section:str, var_name:str, value):
    "Change a var in sys/system.conf and check if pack apply new conf on sys/ files and packed iso."
    global first_unpacked
    global config
    global bootbin_expected_data
    global bi2bin_expected_data
    global apploaderimg_expected_data
    config[section][var_name] = value
    with (first_unpacked / "sys/system.conf").open("w") as conf_file:
        config.write(conf_file)
    repacked_path = repack_path / first_unpacked.name
    gcmtool_pack(first_unpacked, repacked_path)

    apploaderimg_data = (first_unpacked / "sys/apploader.img").read_bytes()
    if (first_unpacked / "sys/boot.bin").read_bytes() != bootbin_expected_data or \
        (first_unpacked / "sys/bi2.bin").read_bytes() != bi2bin_expected_data or \
        apploaderimg_data != apploaderimg_expected_data:
        raise Exception(f"Error - Invalid sys files [{section}][{var_name}] patched value: {value}.")

    apploader_size = int.from_bytes(apploaderimg_data[0x14:0x18], "big") + int.from_bytes(apploaderimg_data[0x18:0x1c], "big") + 32

    with repacked_path.open("rb+") as iso_path:
        if iso_path.read(0x440) != bootbin_expected_data or \
            iso_path.read(0x2000) != bi2bin_expected_data or \
            iso_path.read(apploader_size) != apploaderimg_expected_data:
            raise Exception(f"Error - Invalid iso value after [{section}][{var_name}] patched value: {value}.")
    print(f"Correct [{section}][{var_name}] patched value: {value}.")
    (repack_path / first_unpacked.name).unlink()

bootbin_expected_data[:4] = b"ABCD"
test_config_pack("boot.bin", "GameCode", "ABCD")
bootbin_expected_data[4:6] = b"EF"
test_config_pack("boot.bin", "MakerCode", "EF")
bootbin_expected_data[6:7] = b"\x05"
test_config_pack("boot.bin", "DiscNumber", "5")
bootbin_expected_data[7:8] = b"\x12"
test_config_pack("boot.bin", "GameVersion", "18")
bootbin_expected_data[8:9] = b"\x01"
test_config_pack("boot.bin", "AudioStreaming", "1")
bootbin_expected_data[8:9] = b"\x00"
test_config_pack("boot.bin", "AudioStreaming", "0")
bootbin_expected_data[9:10] = b"\x06"
test_config_pack("boot.bin", "StreamBufferSize", "6")
# test_config_pack("boot.bin", "DVDMagic", )
bootbin_expected_data[0x20:0x60] = b"a b:cdef_ghi-jklmnopqrstuvwxyza b:cdef_ghi-jklmnopqrstuvwxyz0123"
test_config_pack("boot.bin", "GameName", "a b:cdef_ghi-jklmnopqrstuvwxyza b:cdef_ghi-jklmnopqrstuvwxyz0123")
bootbin_expected_data[0x20:0x60] = b"zyxw" + b"\x00" * 60
test_config_pack("boot.bin", "GameName", "zyxw")

dol_offset = int.from_bytes(bootbin_expected_data[0x420:0x424], "big")
with (first_unpacked / "sys/boot.dol").open("rb+") as dol_file:
    dol_file.seek(0x1000)
    dol_file.truncate()

bootbin_expected_data[0x420:0x424] = (dol_offset + 0x200).to_bytes(4, "big")
test_config_pack("boot.bin", "DolOffset", f"0x{dol_offset + 0x200:x}")
bootbin_expected_data[0x424:0x428] = (dol_offset + 0x200 + 0x1000).to_bytes(4, "big")
test_config_pack("boot.bin", "FstOffset", f"0x{dol_offset + 0x200 + 0x1000:x}")

fst_len = int.from_bytes(bootbin_expected_data[0x428:0x42c], "big")
with (first_unpacked / "sys/fst.bin").open("rb+") as fst_file:
    fst_file.seek(fst_len + 0x200)
    fst_file.truncate()

bootbin_expected_data[0x428:0x42c] = (fst_len + 0x200).to_bytes(4, "big")
test_config_pack("boot.bin", "FstLen", f"0x{fst_len + 0x200:x}")
bootbin_expected_data[0x42c:0x430] = b"\xab\xcd\xef\x12"
test_config_pack("boot.bin", "FstMaxLen", "0xabcdef12")
bootbin_expected_data[0x434:0x438] = b"\x98\x76\x54\x32"
test_config_pack("boot.bin", "UserPosition", "0x98765432")
bootbin_expected_data[0x438:0x43c] = b"\xab\xcd\xef\x12"
test_config_pack("boot.bin", "UserLength", "0xabcdef12")

bi2bin_expected_data[:4] = b"\x12\x13\x14\x20"
test_config_pack("bi2.bin", "DebugMonitorSize", "0x12131420")
bi2bin_expected_data[4:8] = b"\x21\x32\x43\x00"
test_config_pack("bi2.bin", "SimulatedMemorySize", "0x21324300")
bi2bin_expected_data[8:12] = b"\x65\x43\x21\x00"
test_config_pack("bi2.bin", "ArgumentOffset", "0x65432100")
bi2bin_expected_data[0xc:0x10] = b"\x00\x00\x00\x03"
test_config_pack("bi2.bin", "DebugFlag", "3")
bi2bin_expected_data[0x10:0x14] = b"\x51\x36\x27\x19"
test_config_pack("bi2.bin", "TrackLocation", "0x51362719")
bi2bin_expected_data[0x14:0x18] = b"\x95\x82\x31\x45"
test_config_pack("bi2.bin", "TrackSize", "0x95823145")
bi2bin_expected_data[0x18:0x1c] = b"\x00\x00\x00\x04"
test_config_pack("bi2.bin", "CountryCode", "4")
bi2bin_expected_data[0x1c:0x20] = b"\x00\x00\x00\x45"
test_config_pack("bi2.bin", "TotalDisc", "45")
bi2bin_expected_data[0x20:0x24] = b"\x00\x00\x00\x01"
test_config_pack("bi2.bin", "LongFileNameSupport", "1")
bi2bin_expected_data[0x20:0x24] = b"\x00\x00\x00\x00"
test_config_pack("bi2.bin", "LongFileNameSupport", "0")
bi2bin_expected_data[0x28:0x2c] = b"\x92\x87\x45\x56"
test_config_pack("bi2.bin", "DolLimit", "0x92874556")

apploaderimg_expected_data[:10] = b"dfghisdfgq"
test_config_pack("apploader.img", "Version", "dfghisdfgq")
apploaderimg_expected_data[:10] = b"123" + b"\x00" * 7
test_config_pack("apploader.img", "Version", "123")
apploaderimg_expected_data[0x10:0x14] = b"\x81\x12\x34\x56"
test_config_pack("apploader.img", "EntryPoint", "0x81123456")
config["apploader.img"]["Size"] = "0x2000"
apploaderimg_expected_data[0x14:0x18] = b"\x00\x00\x20\x00"
apploaderimg_expected_data[0x18:0x1c] = b"\x00\x00\x10\x23"
with (first_unpacked / "sys/apploader.img").open("rb+") as apploaderimg_file:
    apploaderimg_file.seek(0x3043)
    apploaderimg_file.truncate()
    apploaderimg_expected_data = apploaderimg_expected_data[:0x3043]

test_config_pack("apploader.img", "TrailerSize", "0x1023")

print("###############################################################################")
print(f"# TEST 7/{TEST_COUNT}")
print("# Testing system.conf exceptions.")
print("###############################################################################")
gcm = Gcm()
def test_conf_pack_except(section:str, var_name:str, value):
    global first_unpacked
    global config
    
    repacked_path = repack_path / first_unpacked.name

    conf_back = config[section][var_name]
    config[section][var_name] = value
    with (first_unpacked / "sys/system.conf").open("w") as conf_file:
        config.write(conf_file)
    try:
        gcm.pack(first_unpacked, repacked_path)
        raise Exception("Error - InvalidConfValueError should have been triggered.")
    except InvalidConfValueError:
        print("Correct InvalidConfValueError triggered.")

    config[section][var_name] = conf_back
    with (first_unpacked / "sys/system.conf").open("w") as conf_file:
        config.write(conf_file)

test_conf_pack_except("boot.bin", "GameCode", "abcde")
test_conf_pack_except("boot.bin", "MakerCode", "abc")
test_conf_pack_except("boot.bin", "DiscNumber", "99")
test_conf_pack_except("boot.bin", "GameVersion", "100")
test_conf_pack_except("boot.bin", "AudioStreaming", "2")
test_conf_pack_except("boot.bin", "StreamBufferSize", "16")
#test_conf_pack_except("boot.bin", "DVDMagic", )
test_conf_pack_except("boot.bin", "GameName", "a" * 65)
test_conf_pack_except("boot.bin", "DolOffset", "123")
test_conf_pack_except("boot.bin", "DolOffset", "0x180000000")
test_conf_pack_except("boot.bin", "FstOffset", "231")
test_conf_pack_except("boot.bin", "FstOffset", "0x180000000")
test_conf_pack_except("boot.bin", "FstLen", "231")
test_conf_pack_except("boot.bin", "FstLen", "0x180000000")
test_conf_pack_except("boot.bin", "FstMaxLen", "231")
test_conf_pack_except("boot.bin", "FstMaxLen", "0x180000000")
test_conf_pack_except("boot.bin", "UserPosition", "231")
test_conf_pack_except("boot.bin", "UserPosition", "0x180000000")
test_conf_pack_except("boot.bin", "UserLength", "231")
test_conf_pack_except("boot.bin", "UserLength", "0x180000000")

test_conf_pack_except("bi2.bin", "DebugMonitorSize", "231")
test_conf_pack_except("bi2.bin", "DebugMonitorSize", "0x80000001")
test_conf_pack_except("bi2.bin", "DebugMonitorSize", "0x180000000")
test_conf_pack_except("bi2.bin", "SimulatedMemorySize", "231")
test_conf_pack_except("bi2.bin", "SimulatedMemorySize", "0x80000001")
test_conf_pack_except("bi2.bin", "SimulatedMemorySize", "0x180000000")
test_conf_pack_except("bi2.bin", "ArgumentOffset", "231")
test_conf_pack_except("bi2.bin", "ArgumentOffset", "0x180000000")
test_conf_pack_except("bi2.bin", "DebugFlag", "0x1")
test_conf_pack_except("bi2.bin", "DebugFlag", f"{0x1ffffffff}")
test_conf_pack_except("bi2.bin", "TrackLocation", "231")
test_conf_pack_except("bi2.bin", "TrackLocation", "0x180000000")
test_conf_pack_except("bi2.bin", "TrackSize", "231")
test_conf_pack_except("bi2.bin", "TrackSize", "0x180000000")
test_conf_pack_except("bi2.bin", "CountryCode", "3")
test_conf_pack_except("bi2.bin", "CountryCode", "5")
test_conf_pack_except("bi2.bin", "TotalDisc", "100")
test_conf_pack_except("bi2.bin", "TotalDisc", "0x5")
test_conf_pack_except("bi2.bin", "LongFileNameSupport", "3")
test_conf_pack_except("bi2.bin", "DolLimit", "231")
test_conf_pack_except("bi2.bin", "DolLimit", "0x180000000")

test_conf_pack_except("apploader.img", "Version", "a" * 11)
test_conf_pack_except("apploader.img", "EntryPoint", "231")
test_conf_pack_except("apploader.img", "EntryPoint", "0x180000000")
test_conf_pack_except("apploader.img", "Size", "231")
test_conf_pack_except("apploader.img", "Size", "0x180000000")
test_conf_pack_except("apploader.img", "TrailerSize", "231")
test_conf_pack_except("apploader.img", "TrailerSize", "0x180000000")

first_unpacked = unpack_path / "Gotcha Force (Europe) (En,Fr,De).iso"
gcmtool_unpack(roms_path / "Gotcha Force (Europe) (En,Fr,De).iso", first_unpacked)

# | 00002440 | 0001f664 | 0001d224 | apploader.img
# | 0001f700 | 003dcb00 | 003bd400 | boot.dol
# | 003dcb00 | 003dcbaa | 000000aa | fst.bin
# | 003e0000 | 003e1fa0 | 00001fa0 | opening.bnr
# change apploader size & trailer size to match boot.dol
# 1f700 - (2440 + 32) = 1d2a0
with (first_unpacked / "sys/apploader.img").open("rb+") as apploaderimg_file:
    apploaderimg_file.seek(0x14)
    apploaderimg_file.write(b"\x00\x00\xd2\xa0") # size
    apploaderimg_file.write(b"\x00\x01\x00\x00") # trailer_size
    apploaderimg_file.seek(0x1d29f + 32)
    apploaderimg_file.write(b"\x00")
gcmtool_pack(first_unpacked, repack_path / "ok1.iso")
print("Correct apploader patch with max size before dol.")

gcm = Gcm()
# change apploader size & trailer size to overflow 1 byte on boot.dol
with (first_unpacked / "sys/apploader.img").open("rb+") as apploaderimg_file:
    apploaderimg_file.seek(0x14)
    apploaderimg_file.write(b"\x00\x00\xd2\xa1") # size
    apploaderimg_file.seek(0x1d2a0 + 32)
    apploaderimg_file.write(b"\x00")
try:
    gcm.pack(first_unpacked, repack_path / "except.iso")
    raise Exception("Error - ApploaderOverflowError should have been triggered.")
except ApploaderOverflowError:
    print("Correct ApploaderOverflowError triggered: apploader overfloweing on dol.")

# | 00002440 | 0001f701 | 0001f701 | apploader.img
# | 0001f700 | 003dcb00 | 003bd400 | boot.dol
# | 003dcb00 | 003dcbaa | 000000aa | fst.bin
# | 003e0000 | 003e1fa0 | 00001fa0 | opening.bnr
# change apploader size & trailer size to match boot.dol
# 1f700 - (0x2440 + 32) = 2460
gcm = Gcm()
with (first_unpacked / "sys/boot.bin").open("rb+") as bootbin_file:
    bootbin_file.seek(0x420)
    bootbin_file.write(b"\x00\x01\xf8\x00") # dol offset
    bootbin_file.write(b"\x00\x01\xf7\x00") # fst offset
try:
    gcm.pack(first_unpacked, repack_path / "except.iso")
    raise Exception("Error - ApploaderOverflowError should have been triggered.")
except ApploaderOverflowError:
    print("Correct ApploaderOverflowError triggered: apploader overfloweing on fst.")

gcm = Gcm()
with (first_unpacked / "sys/apploader.img").open("rb+") as apploaderimg_file:
    apploaderimg_file.seek(0x14)
    apploaderimg_file.write(b"\x00\x00\xd2\xa0") # size
    apploaderimg_file.seek(0x1d2a0 + 32)
    apploaderimg_file.truncate()
gcm.pack(first_unpacked, repack_path / "ok2.iso")
print("Correct apploader patch with max size before fst.")

fst_length = None
with (first_unpacked / "sys/boot.bin").open("rb+") as bootbin_file:
    bootbin_file.seek(0x428)
    fst_length = int.from_bytes(bootbin_file.read(4), "big")
    bootbin_file.write((fst_length - 1).to_bytes(4, "big")) # fst max len

gcmtool_rebuild_fst(first_unpacked)

with (first_unpacked / "sys/boot.bin").open("rb+") as bootbin_file:
    bootbin_file.seek(0x42c)
    if int.from_bytes(bootbin_file.read(4), "big") != fst_length:
        raise Exception("Error - fst_max_length should have been patched with new fst_length.")
    print("Correct max fst length patched with new fst length.")

    bootbin_file.seek(0x42c)
    bootbin_file.write((fst_length + 1).to_bytes(4, "big")) # fst max len

gcmtool_rebuild_fst(first_unpacked)

dvd_user_length = None
with (first_unpacked / "sys/boot.bin").open("rb") as bootbin_file:
    bootbin_file.seek(0x424) # fst offset
    fst_offset = int.from_bytes(bootbin_file.read(4), "big")
    bootbin_file.seek(0x42c)
    if int.from_bytes(bootbin_file.read(4), "big") != fst_length + 1:
        raise Exception("Error - fst_max_length shouldn't have been patched with new fst_length.")
    print("Correct unpatched max fst length.")

    # By default dol_offset < fst_offset when rebuilding FST
    # So fst_end_offset rounded up == user_position
    # iso_end - user_position = user_length rounded 4 bytes up
    bootbin_file.seek(0x434) # user position
    if int.from_bytes(bootbin_file.read(4), "big") != align_top(fst_offset + fst_length, 4):
        raise Exception("Error - user_position should be aligned after the end of the FST.")
    print("Correct user_position.")
    dvd_user_length = int.from_bytes(bootbin_file.read(4), "big") # user length

user_length = 0
for path in (first_unpacked / "root").glob("**/*"):
    if path.is_file():
        user_length += align_top(path.stat().st_size, 4)

if user_length != dvd_user_length:
    raise Exception(f"Error - Invalid user_length {user_length:x}, {dvd_user_length:x}.")

# Testing conf setup with FST & dol offsets/length
config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
config.optionxform = str # makes options case sensitive
config.read(first_unpacked / "sys/system.conf")
config["Default"]["boot.bin_section"] = "enabled"
config["Default"]["bi2.bin_section"] = "enabled"
config["Default"]["apploader.img_section"] = "enabled"
original_bootbin_data = bytearray( (first_unpacked / "sys/boot.bin").read_bytes() )

# dol_offset = 0x2 00 00
config["boot.bin"]["DolOffset"] = "0x20000"
original_bootbin_data[0x420:0x424] = b"\x00\x02\x00\x00"
# fst_offset = 0x2 00 00 00
config["boot.bin"]["FstOffset"] = "0x2000000"
original_bootbin_data[0x424:0x428] = b"\x02\x00\x00\x00"
# fst_len = 0x10 00 00
config["boot.bin"]["FstLen"] = "0x100000"
original_bootbin_data[0x428:0x42c] = b"\x00\x10\x00\x00"
# fst_max_len = 0x10 00 00
original_bootbin_data[0x42c:0x430] = b"\x00\x10\x00\x00"
# user_position = 0x2 10 00 00
original_bootbin_data[0x434:0x438] = b"\x02\x10\x00\x00"
# user_length = inchanged

with (first_unpacked / "sys/system.conf").open("w") as conf_file:
    config.write(conf_file)

gcmtool_rebuild_fst(first_unpacked)

if (first_unpacked / "sys/boot.bin").read_bytes() != original_bootbin_data:
    raise Exception("Error - Invalid patched boot.bin.")

with (first_unpacked / "sys/fst.bin").open("rb+") as fstbin_file:
    fstbin_file.seek(0xfffff)
    fstbin_file.write(b"\x00")

gcmtool_pack(first_unpacked, repack_path / "ok5.iso")

with (repack_path / "ok5.iso").open("rb") as repack_file:
    if original_bootbin_data != repack_file.read(0x440):
        raise Exception("Error - Invalid repacked iso.")

    dol_data = (first_unpacked / "sys/boot.dol").read_bytes()
    repack_file.seek(0x20000)
    if dol_data != repack_file.read(len(dol_data)):
        raise Exception("Error - Invalid repacked iso.")

    fst_data = (first_unpacked / "sys/fst.bin").read_bytes()
    repack_file.seek(0x2000000)
    if fst_data != repack_file.read(len(fst_data)):
        raise Exception("Error - Invalid repacked iso.")
print("Correct constrained FST after dol with fixed length.")

# user_length = inchanged

# dol_offset = 0x12 00 00
config["boot.bin"]["DolOffset"] = "0x120000"
original_bootbin_data[0x420:0x424] = b"\x00\x12\x00\x00"
# fst_offset = 0x2 00 00
config["boot.bin"]["FstOffset"] = "0x20000"
original_bootbin_data[0x424:0x428] = b"\x00\x02\x00\x00"
# fst_len = 0x10 00 00
config["boot.bin"]["FstLen"] = "0x100000"
original_bootbin_data[0x428:0x42c] = b"\x00\x10\x00\x00"
# fst_max_len = 0x10 00 00
original_bootbin_data[0x42c:0x430] = b"\x00\x10\x00\x00"
# user_position = 0x2 12 00 00
original_bootbin_data[0x434:0x438] = b"\x02\x12\x00\x00"
# user_length = inchanged
# dol_len =  0x2 00 00 00
with (first_unpacked / "sys/boot.dol").open("rb+") as bootdol_file:
    bootdol_file.seek(0x2000000)
    bootdol_file.truncate()

with (first_unpacked / "sys/system.conf").open("w") as conf_file:
    config.write(conf_file)

gcmtool_rebuild_fst(first_unpacked)

if (first_unpacked / "sys/boot.bin").read_bytes() != original_bootbin_data:
    raise Exception("Error - Invalid patched boot.bin.")

with (first_unpacked / "sys/fst.bin").open("rb+") as fstbin_file:
    fstbin_file.seek(0xfffff)
    fstbin_file.write(b"\x00")

gcmtool_pack(first_unpacked, repack_path / "ok6.iso")

with (repack_path / "ok6.iso").open("rb") as repack_file:
    if original_bootbin_data != repack_file.read(0x440):
        raise Exception("Error - Invalid repacked iso.")

    dol_data = (first_unpacked / "sys/boot.dol").read_bytes()
    repack_file.seek(0x120000)
    if dol_data != repack_file.read(len(dol_data)):
        raise Exception("Error - Invalid repacked iso.")

    fst_data = (first_unpacked / "sys/fst.bin").read_bytes()
    repack_file.seek(0x20000)
    if fst_data != repack_file.read(len(fst_data)):
        raise Exception("Error - Invalid repacked iso.")
print("Correct constrained dol after FST with fixed length.")

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
