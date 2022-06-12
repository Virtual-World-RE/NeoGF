from doltool import Dol, MemoryObject, Section, ActionReplayCode
from doltool import SectionType, IntervalDiv
from doltool import InvalidImgOffsetError, InvalidVirtualAddressError, InvalidIniFileEntryError, OutOfMemoryError, InvalidSectionAlignError, SectionsOverflowError
from doltool import parse_action_replay_ini, get_overlapping_arcodes, get_unmapped_intervals

import copy
import os
from pathlib import Path
import shutil
from time import time


__version__ = "0.0.4"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


##################################################
# Installation
##################################################
# Original Gotcha Force "eu.dol" has to be placed in the same folder than this script.
##################################################
# Path of test folder
##################################################
# Dols samples path
dols_path = Path("dol_samples")
# Inis path
ini_path = Path("ini_tests")
# Used to create dols.
dol_tests_path = Path("dol_tests")
# Dols parsed and rebuild path
dols_save_path = Path("dol_save")

##################################################
# doltool.py commands wrappers
##################################################
def doltool_par(dol_path:Path, output_path:Path, ini_path:Path):
    if os.system(f"python doltool.py -par \"{dol_path}\" -o \"{output_path}\" -ini \"{ini_path}\"") != 0:
        raise Exception("Error while patching dol using ARCodes ini file.")
def doltool_par_sr(dol_path:Path, output_path:Path, ini_path:Path):
    if os.system(f"python doltool.py -par \"{dol_path}\" -o \"{output_path}\" -ini \"{ini_path}\" -sr\"") != 0:
        raise Exception("Error while patching dol using ARCodes ini file and section remapping.")

##################################################
# Helpers
##################################################
class DolDescriptor:
    def __init__(self, index:int, offset:int, address:int, length:int, byte:bytes):
        self.index = index
        self.offset = offset + 0x100
        self.address = address
        self.length = length
        self.byte = byte
    def boffset(self):  return self.offset.to_bytes(4,"big")
    def baddress(self): return (self.address + 0x80003100).to_bytes(4,"big")
    def blength(self):  return self.length.to_bytes(4,"big")


def map_offsets(datas:bytes, offsets_map:list, intervals:list):
    'create virtual space temporary to patch then replace as initial mapped with patched datas.'
    max_address = 0
    for beg,length,dest in offsets_map:
        max_address = max(max_address, dest+length)
    remapped_datas = bytearray(b"\x00"*max_address)
    for [beg, length, dest] in offsets_map:
        remapped_datas[dest:dest+length] = datas[beg:beg+length]
    for beg,end,byte in intervals:
        remapped_datas[beg:end] = byte * (end - beg)
    for [beg, length, dest] in offsets_map:
        datas[beg:beg+length] = remapped_datas[dest:dest+length]
    return datas


def create_dol(dol_name:str, descriptors_list:list, bss_addr:int = 20, bss_length:int = 100, entry_point:int = 0):
    """
    input: [DolDescriptor, ...]
    create a dol with specified values in dol_tests_path
    """
    descriptors_list.sort(key=lambda x:x.index)

    offsets = b""
    address = b""
    lengths = b""
    tmp_list = copy.deepcopy(descriptors_list)
    for index in range(18):
        if tmp_list:
            if tmp_list[0].index == index:
                offsets += tmp_list[0].boffset()
                address += tmp_list[0].baddress()
                lengths += tmp_list[0].blength()

                tmp_list.pop(0)
                continue
        offsets += b"\x00\x00\x00\x00"
        address += b"\x00\x00\x00\x00"
        lengths += b"\x00\x00\x00\x00"

    datas = (offsets + address + lengths + (bss_addr + 0x80003100).to_bytes(4,"big") + bss_length.to_bytes(4,"big") + (entry_point + 0x80003100).to_bytes(4,"big")).ljust(0x100, b"\x00")

    descriptors_list.sort(key=lambda x:x.offset)
    for descriptor in descriptors_list:
        if len(datas) != descriptor.offset: raise Exception("doltest.py - Invalid dol creation offset.")
        datas += descriptor.byte * descriptor.length
    Path(dol_tests_path / dol_name).write_bytes(datas)


def to_action_replay_list(memory_objects:list):
    arc_list = []
    for memory_object in memory_objects:
        arc_list.append(ActionReplayCode("04003100 12345678", 0))
        arc_list[-1].set_address(memory_object.address())
        arc_list[-1].set_end_address(memory_object.end_address())
        arc_list[-1].set_datas(b"a" * memory_object.length())
    return arc_list


def memory_objects_to_ini_txt(memory_objects:list):
    str_buffer = ""
    for memory_object in memory_objects:
        addr = memory_object.address() & 0x01FFFFFF
        str_buffer += f""
        if memory_object.length() == 4:
            str_buffer += f"{addr | 0x04000000:08x} " + f"{memory_object.datas()[0]:02x}"*4 + "\n"
        elif memory_object.length() % 2 == 0:
            str_buffer += f"{addr | 0x02000000:08x} {((memory_object.length() // 2) - 1):04x}" + f"{memory_object.datas()[0]:02x}"*2 + "\n"
        else:
            str_buffer += f"{addr:08x} {(memory_object.length() - 1):06x}" + f"{memory_object.datas()[0]:02x}" + "\n"
    return str_buffer


def create_memory_objects_from_intervals(*intervals:list):
    'Create memory objects list from intervals.'
    if intervals is None:
        return None
    res = []
    for interval in intervals:
        memory_object = MemoryObject(0x80003100 + interval[0], end_address = 0x80003100 +  interval[1])
        res.append( memory_object )
        if len(interval) == 3:
            memory_object.set_datas(interval[2] * memory_object.length())
    return res


TEST_COUNT = 8
start = time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if ini_path.is_dir() or dol_tests_path.is_dir() or dols_save_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{ini_path}\n-{dol_tests_path}\n-{dols_save_path}")

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Testing valid dol.resolve_img2virtual conversion.")
print("###############################################################################")
dol = Dol(Path("eu.dol"))
print("Testing first offset of each segments with correct output:")
for (offset, virtual_address) in [(0x100, 0x80003100), (0x25e0, 0x800055e0), (0x2aede0, 0x802b1de0), (0x2aee00, 0x802b1e00), (0x2aee20, 0x802b1e20), (0x2bde80, 0x802c0e80), (0x3b3bc0, 0x8043cbe0), (0x3b66e0, 0x80440080)]:
    if dol.resolve_img2virtual(offset) == virtual_address:
        print("Correct translation")
    else:
        raise Exception(f"Error - resolve_img2virtual invalid translation for offset {offset:08x}: {virtual_address:08x}.")

print("Testing last offset of each segments with correct output:")
for (offset, virtual_address) in [(0x100 + 0x24e0 - 1, 0x800055e0 - 1), (0x25e0 + 0x2ac800 - 1, 0x802b1de0 - 1), (0x2aede0 + 0x20 - 1, 0x802b1e00 - 1), (0x2aee00 + 0x20 - 1, 0x802b1e20 - 1), (0x2aee20 + 0xf060 - 1, 0x802c0e80 - 1), (0x2bde80 + 0xf5d40 - 1, 0x803b6bc0 - 1), (0x3b3bc0 + 0x2b20 - 1, 0x8043f700 - 1), (0x3b66e0 + 0x6d20 - 1, 0x80446da0 - 1)]:
    if dol.resolve_img2virtual(offset) == virtual_address:
        print("Correct translation")
    else:
        raise Exception(f"Error - resolve_img2virtual invalid translation for offset {offset:08x}: {virtual_address:08x}.")

print("Testing first and last offset out of file datas to raise Exception:")
for invalid_offset in [0x9f, 0x3bd400]:
    try:
        dol.resolve_img2virtual(invalid_offset)
        raise Exception("Error - InvalidImgOffsetError Exception should have been triggered.")
    except InvalidImgOffsetError:
        print("Correct InvalidImgOffsetError triggered.")

print("###############################################################################")
print(f"# TEST 2/{TEST_COUNT}")
print("# Testing valid dol.resolve_virtual2img conversion.")
print("###############################################################################")
print("Testing first virtual address of each segments with correct output:")
for (offset, virtual_address) in [(0x100, 0x80003100), (0x25e0, 0x800055e0), (0x2aede0, 0x802b1de0), (0x2aee00, 0x802b1e00), (0x2aee20, 0x802b1e20), (0x2bde80, 0x802c0e80), (0x3b3bc0, 0x8043cbe0), (0x3b66e0, 0x80440080)]:
    if dol.resolve_virtual2img(virtual_address) == offset:
        print("Correct translation")
    else:
        print(f"{dol.resolve_virtual2img(virtual_address):08x}")
        raise Exception(f"Error - resolve_virtual2img invalid translation for offset {virtual_address:08x}:{offset:08x}.")

print("Testing last virtual address of each segments with correct output:")
for (offset, virtual_address) in [(0x100 + 0x24e0 - 1, 0x800055e0 - 1), (0x25e0 + 0x2ac800 - 1, 0x802b1de0 - 1), (0x2aede0 + 0x20 - 1, 0x802b1e00 - 1), (0x2aee00 + 0x20 - 1, 0x802b1e20 - 1), (0x2aee20 + 0xf060 - 1, 0x802c0e80 - 1), (0x2bde80 + 0xf5d40 - 1, 0x803b6bc0 - 1), (0x3b3bc0 + 0x2b20 - 1, 0x8043f700 - 1), (0x3b66e0 + 0x6d20 - 1, 0x80446da0 - 1)]:
    if dol.resolve_virtual2img(virtual_address) == offset:
        print("Correct translation")
    else:
        raise Exception(f"Error - resolve_virtual2img invalid translation for offset {virtual_address:08x}:{offset:08x}.")

print("Testing bounding virtual addresses of non existing offset to raise Exception:")
for invalid_offset in [0x800030ff, 0x803b6bc0, 0x803b6bc0, 0x8043cbe0 - 1, 0x8043f700, 0x80440080 - 1, 0x80446da0, 0x80446dc8, 0x81800000]:
    try:
        dol.resolve_virtual2img(invalid_offset)
        raise Exception("Error - InvalidVirtualAddressError Exception should have been triggered.")
    except InvalidVirtualAddressError:
        print("Correct InvalidVirtualAddressError triggered.")

print("###############################################################################")
print(f"# TEST 3/{TEST_COUNT}")
print("# Testing MemoryObject.")
print("###############################################################################")
print("Testing __init__ & __str__")
# address:int, section_type:SectionType = SectionType.UNMAPPED, name:str = None, length:int = None, end_address:int = None
memory_object1 = MemoryObject(0x80003100 + 100, SectionType.BSS, "abcd", length=10)
if str(memory_object1) != f"| {'abcd'.ljust(11)} | {0x80003100+100:08x} | {0x80003100+110:08x} | {10:08x} |" or memory_object1.type() != SectionType.BSS:
    raise Exception("Invalid MemoryObject constructor or __str__.")

memory_object2 = MemoryObject(0x80003100 + 200, name="efgh", end_address=0x80003100 + 310)
if str(memory_object2) != f"| {'efgh'.ljust(11)} | {0x80003100+200:08x} | {0x80003100+310:08x} | {110:08x} |" or memory_object2.type() != SectionType.UNMAPPED:
    raise Exception("Invalid MemoryObject constructor or __str__.")

print("Testing set_address and set_name")
memory_object1.set_end_address(0x80003100 + 200)
memory_object1.set_name("blah")
if str(memory_object1) != f"| {'blah'.ljust(11)} | {0x80003100+100:08x} | {0x80003100+200:08x} | {100:08x} |":
    raise Exception("Invalid MemoryObject set_end_address.")

print("Testing set_end_address")
memory_object1.set_address(0x80003100 + 150)
if str(memory_object1) != f"| {'blah'.ljust(11)} | {0x80003100+150:08x} | {0x80003100+200:08x} | {50:08x} |":
    raise Exception("Invalid MemoryObject set_address.")

print("Testing OutOfMemoryError")
MemoryObject(0x811fffff, length = 1)
MemoryObject(0x80003100, length = 1)
try:
    MemoryObject(0x800030ff, length = 2)
    raise Exception("Error - OutOfMemoryError should have been triggered.")
except OutOfMemoryError:
    print("Correct OutOfMemoryError triggered.")
try:
    MemoryObject(0x80003000, end_address = 0x80003800)
    raise Exception("Error - OutOfMemoryError should have been triggered.")
except OutOfMemoryError:
    print("Correct OutOfMemoryError triggered.")
try:
    MemoryObject(0x811fff00, end_address = 0x811fff00 + 0x200)
    raise Exception("Error - OutOfMemoryError should have been triggered.")
except OutOfMemoryError:
    print("Correct OutOfMemoryError triggered.")
try:
    MemoryObject(0x811fffff, length = 2)
    raise Exception("Error - OutOfMemoryError should have been triggered.")
except OutOfMemoryError:
    print("Correct OutOfMemoryError triggered.")
try:
    MemoryObject(0x81200000, length = 1)
    raise Exception("Error - OutOfMemoryError should have been triggered.")
except OutOfMemoryError:
    print("Correct OutOfMemoryError triggered.")

print("Testing __sub__:")
interval = MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20)

for [intervals_to_remove, expected_res] in [
    [[[0,10]], [[10,20]]], # Before with match
    [[[20,30]], [[10,20]]], # After with match
    [[[0,10],[20,30]], [[10,20]]], # Before and after
    [[[0,11],[20,30]], [[11,20]]], # left truncate
    [[[0,11],[19,30]], [[11,19]]], # left and right truncate
    [[[0,10],[19,30]], [[10,19]]], # right truncate
    [[[0,11],[12,13],[14,15],[19,30]], [[11,12],[13,14],[15,19]]], # left middle and right truncate
    [[[0,11],[11,13],[13,15],[19,30]], [[15,19]]], # following truncates left truncate rigth truncate
    [[[0,11],[11,13],[13,15],[15,20]], None], # following truncates overlap with end match
    [[[10,13],[13,15],[15,25]], None], # following truncates overlap with begin match
    [[[10,13],[13,15],[15,20]], None], # following truncates in with begin and end match
    [[[11,13],[13,15],[15,19]], [[10,11],[19,20]]], # following truncates in
    [[[10,13],[13,15],[15,19]], [[19,20]]], # following truncates in with begin match
    [[[11,13],[13,15],[15,20]], [[10,11]]], # following truncates in with end match
    [[[0,30]], None], # total overlap overflowing left right
    [[[10,30]], None], # total overlap overflowing left
    [[[0,20]], None], # total overlap overflowing right
    [[[10,20]], None]]: # total match
    res_interval = interval - create_memory_objects_from_intervals( *intervals_to_remove )

    expected_res = create_memory_objects_from_intervals(*expected_res) if expected_res is not None else None
    if expected_res is None and res_interval is None:
        print("Correct result.")
        continue

    if len(res_interval) != len(expected_res):
        raise Exception("Error - Invalid __sub__ result.")

    for index, res_interval in enumerate(res_interval):
        if res_interval.address() != expected_res[index].address() or res_interval.end_address() != expected_res[index].end_address():
            raise Exception("Error - Invalid __sub__ result.")
    print("Correct result.")

interval = MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20)

print("Testing __lt__:")
for interval_lt, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   True], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  True], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  False], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  False], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), False], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), False], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), False], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), False], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), False], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), False], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), False], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), False], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  False], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False]]: # total overlap matching right
    if (interval_lt < interval) != expected_res:
        raise Exception("Error - Invalid __lt__ result.")
    else:
        print("Correct result.")

print("Testing __le__:")
for interval_le, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   False], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  False], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  True], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  True], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  True], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), False], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), False], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), False], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), False], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), False], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), False], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), False], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), False], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  False], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  True]]: # total overlap matching right
    if (interval_le <= interval) != expected_res:
        raise Exception("Error - Invalid __le__ result.")
    else:
        print("Correct result.")

print("Testing __ge__:")
for interval_ge, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   False], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  False], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  False], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  False], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), False], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), False], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), False], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), False], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), True], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), True], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), True], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), False], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), False], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  False], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), True], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False]]: # total overlap matching right
    if (interval_ge >= interval) != expected_res:
        raise Exception("Error - Invalid __ge__ result.")
    else:
        print("Correct result.")

print("Testing __gt__:")
for interval_gt, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   False], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  False], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  False], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  False], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), False], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), False], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), False], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), False], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), False], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), False], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), True], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), True], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  False], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False]]: # total overlap matching right
    if (interval_gt > interval) != expected_res:
        raise Exception("Error - Invalid __gt__ result.")
    else:
        print("Correct result.")

print("Testing __contains__:")
for interval_contains, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   False], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  False], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  False], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  False], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), True], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), True], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), True], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), True], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), False], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), False], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), False], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), False], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  False], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), False], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  False]]: # total overlap matching right
    if (interval_contains in interval) != expected_res:
        raise Exception("Error - Invalid __contains__ result.")
    else:
        print("Correct result.")

print("Testing __and__:")
for interval_and, expected_res in [
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9),   False], # __lt__
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10),  False], # __lt__ matching
    [MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11),  True], # __le__ + 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11),  True], # __le__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  True], # __le__ - 1 byte with matching
    [MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19), True], # __contains__
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15), True], # __contains__ matching left
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), True], # __contains__ matching left and right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), True], # __contains__ matching right
    [MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21), True], # __ge__ + 1 byte
    [MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21), True], # __ge__ + 1 byte - 1 byte
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), True], # __ge__ + 1 byte with matching
    [MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25), False], # __gt__ matching
    [MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25), False], # __gt__
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21),  True], # total overlap
    [MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21), True], # total overlap matching left
    [MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20),  True]]: # total overlap matching right
    if (interval_and & interval) != expected_res:
        raise Exception("Error - Invalid __and__ result.")
    else:
        print("Correct result.")

print("Testing __truediv__:")
intervals_truediv = []
intervals_truediv.append( MemoryObject(0x80003100 + 0, end_address=0x80003100 + 9) )
intervals_truediv[0].set_datas(b"l"*9)
intervals_truediv.append( MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10) )
intervals_truediv[1].set_datas(b"l"*10)
intervals_truediv.append( MemoryObject(0x80003100 + 0, end_address=0x80003100 + 11) )
intervals_truediv[2].set_datas(b"l"*10 + b"i")
intervals_truediv.append( MemoryObject(0x80003100 + 9, end_address=0x80003100 + 11) )
intervals_truediv[3].set_datas(b"l" + b"i")
intervals_truediv.append( MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20) )
intervals_truediv[4].set_datas(b"l" + 10*b"i")
intervals_truediv.append( MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19) )
intervals_truediv[5].set_datas(b"i"*8)
intervals_truediv.append( MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15) )
intervals_truediv[6].set_datas(b"i"*5)
intervals_truediv.append( MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20) )
intervals_truediv[7].set_datas(b"i"*10)
intervals_truediv.append( MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20) )
intervals_truediv[8].set_datas(b"i"*5)
intervals_truediv.append( MemoryObject(0x80003100 + 15, end_address=0x80003100 + 21) )
intervals_truediv[9].set_datas(b"i"*5 + b"r")
intervals_truediv.append( MemoryObject(0x80003100 + 19, end_address=0x80003100 + 21) )
intervals_truediv[10].set_datas(b"i" + b"r")
intervals_truediv.append( MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21) )
intervals_truediv[11].set_datas(b"i"*10 + b"r")
intervals_truediv.append( MemoryObject(0x80003100 + 20, end_address=0x80003100 + 25) )
intervals_truediv[12].set_datas(b"r"*5)
intervals_truediv.append( MemoryObject(0x80003100 + 21, end_address=0x80003100 + 25) )
intervals_truediv[13].set_datas(b"r"*4)
intervals_truediv.append( MemoryObject(0x80003100 + 9, end_address=0x80003100 + 21) )
intervals_truediv[14].set_datas(b"l" + b"i"*10 + b"r")
intervals_truediv.append( MemoryObject(0x80003100 + 10, end_address=0x80003100 + 21) )
intervals_truediv[15].set_datas(b"i"*10 + b"r")
intervals_truediv.append( MemoryObject(0x80003100 + 9, end_address=0x80003100 + 20) )
intervals_truediv[16].set_datas(b"l" + b"i"*10)

expected_truediv_res = []
expected_truediv_res.append(None) # __lt__
expected_truediv_res.append(None) # __lt__ matching

# __le__ + 1 byte
expected_truediv_res.append({IntervalDiv.LEFT: MemoryObject(0x80003100 + 0, end_address=0x80003100 + 10), IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 11)})
expected_truediv_res[2][IntervalDiv.LEFT].set_datas(b"l"*10)
expected_truediv_res[2][IntervalDiv.IN].set_datas(b"i")

# __le__ + 1 byte - 1 byte
expected_truediv_res.append({IntervalDiv.LEFT: MemoryObject(0x80003100 + 9, end_address=0x80003100 + 10), IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 11)})
expected_truediv_res[3][IntervalDiv.LEFT].set_datas(b"l")
expected_truediv_res[3][IntervalDiv.IN].set_datas(b"i")

# __le__ - 1 byte with matching
expected_truediv_res.append({IntervalDiv.LEFT: MemoryObject(0x80003100 + 9, end_address=0x80003100 + 10), IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20)})
expected_truediv_res[4][IntervalDiv.LEFT].set_datas(b"l")
expected_truediv_res[4][IntervalDiv.IN].set_datas(b"i"*10)

# __contains__
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 11, end_address=0x80003100 + 19)})
expected_truediv_res[5][IntervalDiv.IN].set_datas(b"i"*8)

# __contains__ matching left
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 15)})
expected_truediv_res[6][IntervalDiv.IN].set_datas(b"i"*5)

# __contains__ matching left and right
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20)})
expected_truediv_res[7][IntervalDiv.IN].set_datas(b"i"*10)

# __contains__ matching right
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20)})
expected_truediv_res[8][IntervalDiv.IN].set_datas(b"i"*5)

# __ge__ + 1 byte
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 15, end_address=0x80003100 + 20), IntervalDiv.RIGHT: MemoryObject(0x80003100 + 20, end_address=0x80003100 + 21)})
expected_truediv_res[9][IntervalDiv.IN].set_datas(b"i"*5)
expected_truediv_res[9][IntervalDiv.RIGHT].set_datas(b"r")

# __ge__ + 1 byte - 1 byte
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 19, end_address=0x80003100 + 20), IntervalDiv.RIGHT: MemoryObject(0x80003100 + 20, end_address=0x80003100 + 21)})
expected_truediv_res[10][IntervalDiv.IN].set_datas(b"i")
expected_truediv_res[10][IntervalDiv.RIGHT].set_datas(b"r")

# __ge__ + 1 byte with matching
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), IntervalDiv.RIGHT: MemoryObject(0x80003100 + 20, end_address=0x80003100 + 21)})
expected_truediv_res[11][IntervalDiv.IN].set_datas(b"i"*10)
expected_truediv_res[11][IntervalDiv.RIGHT].set_datas(b"r")

expected_truediv_res.append(None) # __gt__ matching
expected_truediv_res.append(None) # __gt__

# total overlap
expected_truediv_res.append({IntervalDiv.LEFT: MemoryObject(0x80003100 + 9, end_address=0x80003100 + 10), IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), IntervalDiv.RIGHT: MemoryObject(0x80003100 + 20, end_address=0x80003100 + 21)})
expected_truediv_res[14][IntervalDiv.LEFT].set_datas(b"l")
expected_truediv_res[14][IntervalDiv.IN].set_datas(b"i"*10)
expected_truediv_res[14][IntervalDiv.RIGHT].set_datas(b"r")

# total overlap matching left
expected_truediv_res.append({IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20), IntervalDiv.RIGHT: MemoryObject(0x80003100 + 20, end_address=0x80003100 + 21)})
expected_truediv_res[15][IntervalDiv.IN].set_datas(b"i"*10)
expected_truediv_res[15][IntervalDiv.RIGHT].set_datas(b"r")

# total overlap matching right
expected_truediv_res.append({IntervalDiv.LEFT: MemoryObject(0x80003100 + 9, end_address=0x80003100 + 10), IntervalDiv.IN: MemoryObject(0x80003100 + 10, end_address=0x80003100 + 20)})
expected_truediv_res[16][IntervalDiv.LEFT].set_datas(b"l")
expected_truediv_res[16][IntervalDiv.IN].set_datas(b"i"*10)

for index in range(len(expected_truediv_res)):
    interval_truediv = intervals_truediv[index]
    expected_res = expected_truediv_res[index]

    new_intervals = interval_truediv / interval
    if expected_res is None and new_intervals is None:
        print("Correct result")
        continue

    for key in expected_res.keys():
        if key not in new_intervals:
            raise Exception("Error - Invalid __truediv__ result.")
        if new_intervals[key].address() != expected_res[key].address() or new_intervals[key].end_address() != expected_res[key].end_address() or new_intervals[key].datas() != expected_res[key].datas():
            raise Exception("Error - Invalid __truediv__ result.")
        print("Correct result.")

print("Testing to_memory_object:")
memory_object3 = MemoryObject(0x80003100 + 20, end_address=0x80003100 + 42)

print("Testing set_datas:")
memory_object3.set_datas(b"11333333333333333333BB")
if memory_object3.datas() != b"11333333333333333333BB":
    raise Exception("Error - Invalid set_datas result.")
print("Correct result.")

memory_object3.set_datas(b"00112233445566778899AA")
if memory_object3.datas() != b"00112233445566778899AA":
    raise Exception("Error - Invalid set_datas result.")
print("Correct result.")

print("Testing update_datas:")
update = MemoryObject(0x80003100 + 21, end_address=0x80003100 + 41)
update.set_datas(b"cccccccccccccccccccc")
memory_object3.update_datas(update)
if memory_object3.datas() != b"0ccccccccccccccccccccA":
    raise Exception("Error - Invalid update_datas result.")
print("Correct result.")

update.set_datas(b"9999999999999999999999")
update.set_address(0x80003100 + 20)
update.set_end_address(0x80003100 + 42)
memory_object3.update_datas(update)
if memory_object3.datas() != b"9999999999999999999999":
    raise Exception("Error - Invalid update_datas result.")
print("Correct result.")

print("Testing align:")
memory_object3.set_address(0x80003100 + 3)
memory_object3.set_end_address(0x80003100 + 9)
memory_object3.align()
if memory_object3.address() != 0x80003100 + 0 or memory_object3.end_address() != 0x80003100 + 32:
    raise Exception("Error - Invalid align result.")
print("Correct result.")

print("###############################################################################")
print(f"# TEST 4/{TEST_COUNT}")
print("# Testing valid action_replay_code parsing.")
print("###############################################################################")
ini_path.mkdir()
dol_tests_path.mkdir()
valid_action_replay_ini = "[ActionReplay_Enabled]\n$Costs\n$HP\n$B Ammo and Refill Codes\n$B Mode and Reload Codes\n"+\
    "$X Ammo and Refill Codes\n$X Mode and Reload Codes\n$Warehouse Full\n\n[ActionReplay]\n$Costs\n022E2CC0 00050096\n"+\
    "022E2CCC 00050136\n022E2CD8 0005012C\n022E2CE4 000500D2\n042E4E2A 0000005A\n042E4F92 000001E0\n042E50FA 0000005A\n"+\
    "042E5262 0001003C\n042E53CA 00000078\n042E5532 0000003C\n042E569A 0000003C\n042E5802 00000078\n042E596A 0000000A\n"+\
    "003CE5C2 00000003\n0040E5C2 00000344\n"

(ini_path / "test1.ini").write_text(valid_action_replay_ini)
action_replay_list = parse_action_replay_ini(ini_path / "test1.ini")

expected_res6 = [
    (int("802E2CC0", 16), b"\x00\x96\x00\x96\x00\x96\x00\x96\x00\x96\x00\x96"),
    (int("802E2CCC", 16), b"\x01\x36\x01\x36\x01\x36\x01\x36\x01\x36\x01\x36"),
    (int("802E2CD8", 16), b"\x01\x2C\x01\x2C\x01\x2C\x01\x2C\x01\x2C\x01\x2C"),
    (int("802E2CE4", 16), b"\x00\xD2\x00\xD2\x00\xD2\x00\xD2\x00\xD2\x00\xD2"),
    (int("802E4E2A", 16), b"\x00\x00\x00\x5A"),
    (int("802E4F92", 16), b"\x00\x00\x01\xE0"),
    (int("802E50FA", 16), b"\x00\x00\x00\x5A"),
    (int("802E5262", 16), b"\x00\x01\x00\x3C"),
    (int("802E53CA", 16), b"\x00\x00\x00\x78"),
    (int("802E5532", 16), b"\x00\x00\x00\x3C"),
    (int("802E569A", 16), b"\x00\x00\x00\x3C"),
    (int("802E5802", 16), b"\x00\x00\x00\x78"),
    (int("802E596A", 16), b"\x00\x00\x00\x0A"),
    (int("803CE5C2", 16), b"\x03"),
    (int("8040E5C2", 16), b"\x44\x44\x44\x44")]
if len(expected_res6) != len(action_replay_list):
    raise Exception("Error - Invalid ini parsing.")
for index, exp_res in enumerate(expected_res6):
    if action_replay_list[index].address() != expected_res6[index][0] or action_replay_list[index].datas() != expected_res6[index][1]:
        raise Exception("Error - Invalid ini parsing.")
print("Valid parsing as Expected.")

for invalid_action_replay_ini in ["a\n082E2CC0 00050096\n","0A02E2CC0 00050096","082E2CC0  00050096", "\n122E2CC0 00050096\n"]:
    try:
        (ini_path / "test2.ini").write_text(invalid_action_replay_ini)
        parse_action_replay_ini(ini_path / "test2.ini")
        raise Exception("Error - InvalidIniFileEntryError Exception should have been triggered.")
    except InvalidIniFileEntryError:
        print("Correct InvalidIniFileEntryError triggered.")
# 41200000
for invalid_action_replay_ini in ["\n020030ff 00050096\n","05200000 00050096","05800000 00050096", "\n02000000 04050096\n"]:
    try:
        (ini_path / "test3.ini").write_text(invalid_action_replay_ini)
        parse_action_replay_ini(ini_path / "test3.ini")
        raise Exception("Error - OutOfMemoryError Exception should have been triggered.")
    except OutOfMemoryError:
        print("Correct OutOfMemoryError triggered.")

print("###############################################################################")
print(f"# TEST 5/{TEST_COUNT}")
print("# Testing intervals functions.")
print("###############################################################################")
print("Testing _Dol__get_merged_mapped_memory.")
# There is always sections
# * Sections never overlap
# * unsorted intervals

create_dol("dol0.dol", [
    DolDescriptor(index=0, offset=107, address=160, length=40, byte=b"a"),  # [160, 200] # * > 1 spacing
    DolDescriptor(index=1, offset=95,  address=128, length=12, byte=b"b"),  # [128, 140] # * 0 spacing x2
    DolDescriptor(index=3, offset=63,  address=96, length=32, byte=b"b"),  # [96, 128] # * 0 spacing
    DolDescriptor(index=5, offset=0,   address=32, length=31, byte=b"c"),  # [32, 63] 
    DolDescriptor(index=7, offset=31,  address=64, length=32, byte=b"d")]) # [64, 96] # * 1 spacing between two intervals
expected_res7 = create_memory_objects_from_intervals([32,63],[64,140],[160,200])

dol0 = Dol(dol_tests_path / "dol0.dol")
merged_list = dol0._Dol__get_merged_mapped_memory()

if len(expected_res7) != len(merged_list):
    raise Exception("Error - Invalid merged_list.")

for index, merged in enumerate(merged_list):
    if merged.address() != expected_res7[index].address() or merged.end_address() != expected_res7[index].end_address():
        raise Exception("Error - Invalid intervals merge.")
print("Correct result.")

print("Testing get_overlapping_arcodes.")
arcode0 = ActionReplayCode("04003100 AAAAAAAA", 1)
arcode1 = ActionReplayCode("04003104 BBBBBBBB", 2) # matching
arcode2 = ActionReplayCode("04003107 BBBBBBBB", 3) # overlapping from 1 byte
arcode3 = ActionReplayCode("0400310C BBBBBBBB", 4) # interval 1 byte
arcode4 = ActionReplayCode("0400310C BBBBBBBB", 5) # total overlap
arcode5 = ActionReplayCode("0400310E BBBBBBBB", 6) # overlapping from 2 bytes
arcode6 = ActionReplayCode("02003114 000FBBBB", 7) # overlapping totaly next
arcode7 = ActionReplayCode("04003118 ABCFBBBB", 8) # totaly overlapped

expected_res8 = [[arcode1, arcode2], [arcode3, arcode4], [arcode4, arcode5], [arcode6, arcode7]]

overlaps0 = get_overlapping_arcodes([arcode0,arcode1,arcode2,arcode3,arcode4,arcode5,arcode6,arcode7])
if len(overlaps0) != len(expected_res8):
    raise Exception("Error - Invalid get_overlapping_arcodes result.")

for index, (overlap0, overlap1) in enumerate(overlaps0):
    if overlap0 != expected_res8[index][0] or overlap1 != expected_res8[index][1]:
        raise Exception("Error - Invalid get_overlapping_arcodes result.")

print("Testing get_unmapped_intervals.")
merged_memo_res = [[ # Testing all limits
    create_memory_objects_from_intervals([50,75],[100,200],[250,260],[270,280],[300,400]),
    create_memory_objects_from_intervals(
    [0,5], # before all intervals group
    [10,12],[15,20], [25,50], # map before
    # in group
    [50,75], # in with begin and end map
    # new group
    [80,90], # between group
    [91,92], # between group
    [94,95], # between group
    [95,101], # overlap begining with 1 byte
    # in group
    [101,195], # in match previous interval to test end and next interval to test begin
    [195,200], # in with end map
    # empty group
    [250,258], # in with begin map
    # new group
    [259,264], # overlap ending with 1 byte
    # new group
    [280,285], # map after
    # new group
    [420,430], # after group
    [450,470]),
    create_memory_objects_from_intervals([0,50],[80,100],[260,264],[280,285],[420,470]),
    ],[ # All before with overlap
    create_memory_objects_from_intervals([75,200],[250,260],[270,280]),
    create_memory_objects_from_intervals([0,5],[10,12],[15,20],[25,50],[50,76]),
    create_memory_objects_from_intervals([0,75])
    ],[ # All after with overlap
    create_memory_objects_from_intervals([50,75],[100,120],[140,196]),
    create_memory_objects_from_intervals([195,200],[250,258],[259,264],[450,470]),
    create_memory_objects_from_intervals([196,470])
    ],[ # All between with overlap
    create_memory_objects_from_intervals([10,20],[50,196],[469,520],[600,700]),
    create_memory_objects_from_intervals(
    [195,200], # before overlap
    [250,258], # between
    [259,264], # between
    [450,470]), # after overlap
    create_memory_objects_from_intervals([196, 469])
    ],[ # All between with begin and end match
    create_memory_objects_from_intervals([10,20],[50,196],[469,520],[600,700]),
    create_memory_objects_from_intervals([196,200], [250,258], [259,264], [450,469]),
    create_memory_objects_from_intervals([196, 469])
    ],[ # All in
    create_memory_objects_from_intervals([0,500]),
    create_memory_objects_from_intervals([195,200],[250,258],[259,264],[450,470]),
    None
    ]]
for merged_intervals, memory_objects_list, expected_res in merged_memo_res:
    unmapped_intervals = get_unmapped_intervals(merged_intervals, to_action_replay_list(memory_objects_list))
    if expected_res is None and unmapped_intervals is None:
        print("Corrects get_unmapped_intervals test.")
        continue

    if len(unmapped_intervals) != len(expected_res):
        raise Exception(f"Error - get_unmapped_intervals invalid result.")

    for index, unmapped_interval in enumerate(unmapped_intervals):
        if expected_res[index].address() != unmapped_interval.address() or expected_res[index].end_address() != unmapped_interval.end_address():
            raise Exception(f"Error - get_unmapped_intervals invalid result.")
    print("Corrects get_unmapped_intervals test.")

print("###############################################################################")
print(f"# TEST 6/{TEST_COUNT}")
print("# Testing Section align.")
print("###############################################################################")
# index:int, offset:int, address:int, length:int)

try:
    Section(0, 0x1000, 0x80003101, 10)
except InvalidSectionAlignError:
    print("Correct invalid Section align.")
try:
    Section(0, 0x1000, 0x8000311F, 10)
except InvalidSectionAlignError:
    print("Correct invalid Section align.")

print("###############################################################################")
print(f"# TEST 7/{TEST_COUNT}")
print("# Testing dol._Dol__save.")
print("###############################################################################")
dols_save_path.mkdir()
for input_path in dols_path.glob("*"):
    dol = Dol(input_path)
    dol._Dol__save(dols_save_path / input_path.name)
    if input_path.read_bytes() != (dols_save_path / input_path.name).read_bytes():
        raise Exception(f"Error - Invalid dol parsing and save for dol {input_path}.")
    else:
        print(f"Correct parsing and saving.")

print("###############################################################################")
print(f"# TEST 8/{TEST_COUNT}")
print("# Testing --patch-action-replay commands.")
print("###############################################################################")
# Testing correct patch between two section + 1
# Sections: [0, 32], [32, 64], [64, 96], [96, 128], [128, 160], [160, 192], [192, 224], [224, 256], [256, 288],
# [288, 320], [320, 352], [352, 384], [384, 416], [416, 448]
print("Following sections sorted with offset == address; offset != address and so on.")
# Following sections sorted by offset
create_dol("dol1.dol", [
    DolDescriptor(index=0,  offset=0,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=2,  offset=32,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=3,  offset=64,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=5,  offset=96,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=8,  offset=128, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=9,  offset=160, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=10, offset=192, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=11, offset=224, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=12, offset=256, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=13, offset=288, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=14, offset=320, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=15, offset=352, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=16, offset=384, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=17, offset=416, address=416, length=32, byte=b"\xE0")])
# Following sections reverse sorted by offset
# Here there can't be out overlappings because of address sorting.
create_dol("dol2.dol", [
    DolDescriptor(index=0, offset=416, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=2, offset=384, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=3, offset=352, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=5, offset=320, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=8, offset=288, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=9, offset=256, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=10, offset=224, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=11, offset=192, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=12,  offset=160, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=13,  offset=128, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=14,  offset=96,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=15,  offset=64,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=16,  offset=32,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=17,  offset=0,   address=0,   length=32, byte=b"\x10")])
# Following sections shuffled
# Here there can't be out overlappings because of address sorting.
# Following sections unsorted by offset
create_dol("dol3.dol", [
    DolDescriptor(index=0, offset=192, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=2,  offset=64,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=3,  offset=160, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=5, offset=288, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=8,  offset=128, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=9,  offset=32,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=10,  offset=96,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=11, offset=224, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=12, offset=416, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=13, offset=352, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=14, offset=320, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=15, offset=384, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=16,  offset=0,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=17, offset=256, address=256, length=32, byte=b"\x90")])


mappeurs_dict = {}

# Sames as previously but with offset reverse sorted / shuffled / from addresses
create_dol("dol4.dol", [
    DolDescriptor(index=0,  offset=416,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=2,  offset=384,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=3,  offset=352,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=5,  offset=320,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=8,  offset=288, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=9,  offset=256, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=10, offset=224, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=11, offset=192, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=12, offset=160, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=13, offset=128, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=14, offset=96, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=15, offset=64, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=16, offset=32, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=17, offset=0, address=416, length=32, byte=b"\xE0")])
mappeurs_dict[4] = [
    [416, 32, 0],
    [384, 32, 32],
    [352, 32, 64],
    [320, 32, 96],
    [288, 32, 128],
    [256, 32, 160],
    [224, 32, 192],
    [192, 32, 224],
    [160, 32, 256],
    [128, 32, 288],
    [96, 32, 320],
    [64, 32, 352],
    [32, 32, 384],
    [0, 32, 416]]

create_dol("dol5.dol", [
    DolDescriptor(index=0, offset=0, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=2, offset=32, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=3, offset=64, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=5, offset=96, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=8, offset=128, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=9, offset=160, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=10, offset=192, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=11, offset=224, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=12,  offset=256, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=13,  offset=288, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=14,  offset=320,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=15,  offset=352,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=16,  offset=384,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=17,  offset=416,   address=0,   length=32, byte=b"\x10")])
mappeurs_dict[5] = [
    [0, 32, 416],
    [32, 32, 384],
    [64, 32, 352],
    [96, 32, 320],
    [128, 32, 288],
    [160, 32, 256],
    [192, 32, 224],
    [224, 32, 192],
    [256, 32, 160],
    [288, 32, 128],
    [320, 32, 96],
    [352, 32, 64],
    [384, 32, 32],
    [416, 32, 0]]

create_dol("dol6.dol", [
    DolDescriptor(index=0, offset=416, address=192, length=32, byte=b"\x70"),
    DolDescriptor(index=2,  offset=0,  address=64,  length=32, byte=b"\x30"),
    DolDescriptor(index=3,  offset=192, address=160, length=32, byte=b"\x60"),
    DolDescriptor(index=5, offset=160, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=8,  offset=128, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=9,  offset=64,  address=32,  length=32, byte=b"\x20"),
    DolDescriptor(index=10,  offset=320,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=11, offset=384, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=12, offset=224, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=13, offset=32, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=14, offset=96, address=320, length=32, byte=b"\xB0"),
    DolDescriptor(index=15, offset=288, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=16,  offset=352,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=17, offset=256, address=256, length=32, byte=b"\x90")])
mappeurs_dict[6] = [
    [416, 32, 192],
    [0, 32, 64],
    [192, 32, 160],
    [160, 32, 288],
    [128, 32, 128],
    [64, 32, 32],
    [320, 32, 96],
    [384, 32, 224],
    [224, 32, 416],
    [32, 32, 352],
    [96, 32, 320],
    [288, 32, 384],
    [352, 32, 0],
    [256, 32, 256]]

# Here there can't be out overlappings. 
# Beginning of dol file   # [0, 24]   24 \x11
# Middle   -1 + 1         # [33, 63]  30 \x22
# Middle                  # [80, 84]   4 \x33
# Overlapping + 1         # [93, 97]   4 \x44
# Overlapping - 1         # [127, 131] 4 \x55
# Endin map               # [156, 160] 4 \x66
# Begin map               # [160, 164] 4 \x77
# Begin and ending map    # [192, 224] 32 \x88
# Total overlapping +1 -1 # [255, 289] 34 \x99
# Total overlapping 3 sec # [319, 417] 98 \xAA
# Ending of dol file      # [444, 448] 4 \xBB
# [[begin, end, byte], ...]
intervals_list = []
intervals_list.append([[0, 24, b"\x11"], [33, 63, b"\x22"], [80, 84, b"\x33"], [93, 97, b"\x44"], 
    [127, 131, b"\x55"], [156, 160, b"\x66"], [160, 164, b"\x77"], [192, 224, b"\x88"], 
    [255, 289, b"\x99"], [319, 417, b"\xAA"], [444, 448, b"\xBB"]])
# same reverse sorted
intervals_list.append(sorted(intervals_list[0], key=lambda x: x, reverse=True))
# same but shuffled
intervals_list.append([[156, 160, b"\x66"], [255, 289, b"\x99"], [160, 164, b"\x77"], [93, 97, b"\x44"],\
    [444, 448, b"\xBB"], [80, 84, b"\x33"], [319, 417, b"\xAA"], [33, 63, b"\x22"],\
    [0, 24, b"\x11"], [127, 131, b"\x55"], [192, 224, b"\x88"]])

# just to remember, sames sections:
#     [0, 32], [32, 64], [64, 96], [96, 128], [128, 160], [160, 192], [192, 224], [224, 256], [256, 288],
#     [288, 320], [320, 352], [352, 384], [384, 416], [416, 448]
intervals_list.append([
    [24, 64, b"\x11"],  # overlap left match right
    [96, 130, b"\x22"], # overlap right match left
    [120, 170, b"\x33"], # overlap left and right
    [191, 225, b"\x44"], # overlap left and right +1-1
    [255, 353, b"\x55"]]) # overlap left and right +- 3 sections (reversed)
intervals_list.append([ # same but reverse sorted
    [255, 353, b"\x11"], # overlap left and right +- 3 sections (reversed)
    [191, 225, b"\x22"], # overlap left and right +1-1
    [120, 170, b"\x33"], # overlap left and right
    [96, 130, b"\x44"], # overlap right match left
    [24, 64, b"\x55"]])  # overlap left match right
intervals_list.append([ # same but shuffled
    [120, 170, b"\x11"], # overlap left and right
    [255, 353, b"\x22"], # overlap left and right +- 3 sections (reversed)
    [96, 130, b"\x33"], # overlap right match left
    [24, 64, b"\x44"],  # overlap left match right
    [191, 225, b"\x55"]]) # overlap left and right +1-1
# total file patch
# overlap right (match left) 3 sections dol1 <- sorted
# overlap left match right 3 sections dol3 <- reverse sorted
intervals_list.append([[0, 448, b"\x11"]])
# overlap left and right +3 sections
# overlap left and right -3 sections
intervals_list.append([[254, 448, b"\x11"]])
# overlap left and right +-3 sections <- dol2 1st section
intervals_list.append([[100, 340, b"\x11"]])
# one byte patch test
intervals_list.append([[100, 101, b"\x11"], [105, 110, b"\x22"]])

"""
dol123_datas = b"".join(list(map(lambda x: x.to_bytes(4, "big"), [
    0x100+0, 0, 0x100+32, 0x100+64, 0, 0x100+96, 0, 0, 0x100+128, 0x100+160, 0x100+192, 0x100+224, 0x100+256, 0x100+288, 0x100+320, 0x100+352, 0x100+384, 0x100+416,
    0x80003100+0, 0, 0x80003100+32, 0x80003100+64, 0, 0x80003100+96, 0, 0, 0x80003100+128, 0x80003100+160, 0x80003100+192, 0x80003100+224, 0x80003100+256, 0x80003100+288, 0x80003100+320, 0x80003100+352, 0x80003100+384, 0x80003100+416,  
    32, 0, 32, 32, 0, 32, 0, 0, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32,
    0x80003100+20,100, 0x80003100]))).ljust(0x100, b"\x00") + b"\x10"*32 + b"\x20"*32 + \
    b"\x30"*32 + b"\x40"*32 + b"\x50"*32 + b"\x60"*32 + b"\x70"*32 + b"\x80"*32 + b"\x90"*32 + b"\xA0"*32 + b"\xB0"*32 + \
    b"\xC0"*32 + b"\xD0"*32 + b"\xE0"*32
"""
def test_dols(range_dols, intervals_list:list):
    for interval_index, intervals in enumerate(intervals_list):
        for dol_index in range_dols:
            dol_path         = f"dol{dol_index}.dol"
            dol_patched_path = f"dol{dol_index}_{interval_index}_patched.dol"
            dol_ini_path     = f"dol{dol_index}_{interval_index}.ini"

            # write ini file with same sorting than intervals
            (ini_path / dol_ini_path).write_text( memory_objects_to_ini_txt(create_memory_objects_from_intervals(*intervals)) )

            dol_datas = bytearray((dol_tests_path / dol_path).read_bytes())
            dol_header = dol_datas[:0x100]
            dol_datas = dol_datas[0x100:]

            if dol_index in mappeurs_dict:
                dol_datas = map_offsets(dol_datas, mappeurs_dict[dol_index], intervals)
            else:
                for beg,end,byte in intervals:
                    dol_datas[beg:end] = byte * (end - beg)

            Path(dol_tests_path / f"dol{dol_index}_{interval_index}_patched.dol.expected").write_bytes(dol_header + dol_datas)

            doltool_par(dol_tests_path / dol_path, dol_tests_path / dol_patched_path, ini_path / dol_ini_path)
            if dol_header + dol_datas != (dol_tests_path / dol_patched_path).read_bytes():
                print(interval_index, intervals)
                raise Exception("Error - Invalid -par result.")
test_dols(range(1,7), intervals_list)
# Testing Overflowing at the end of section + 1
intervals_list = []
intervals_list.append([[445, 449, b"\x11"], [33, 63, b"\x22"]])
intervals_list.append([[0, 24, b"\x11"], [445, 449, b"\x22"]])
intervals_list.append([[0, 24, b"\x11"], [447, 451, b"\x22"]])
intervals_list.append([[447, 451, b"\x11"], [33, 63, b"\x22"]])
intervals_list.append([[447, 451, b"\x11"]])
intervals_list.append([[445, 449, b"\x11"]])
intervals_list.append([[446, 449, b"\x11"]])
intervals_list.append([[447, 450, b"\x11"]])
intervals_list.append([[447, 456, b"\x11"]])

for interval_index, intervals in enumerate(intervals_list):
    for dol_index in range(1,7):
        try:
            dol_ini_path = f"dol{dol_index}_{interval_index}_exception.ini"
            (ini_path / dol_ini_path).write_text( memory_objects_to_ini_txt(create_memory_objects_from_intervals(*intervals)) )

            dol = Dol(dol_tests_path / f"dol{dol_index}.dol")

            action_replay_list = parse_action_replay_ini(ini_path / dol_ini_path)
            dol.patch_memory_objects(dol_tests_path / f"dol{dol_index}_patched.dol", action_replay_list)

            raise Exception("Error - SectionsOverflowError Exception should have been triggered.")
        except SectionsOverflowError:
            print("Correct SectionsOverflowError triggered.")

mappeurs_dict = {}
# Sections: [0, 32], [96, 128], [128, 160], [224, 256], [256, 288], [288, 320], [352, 384], [384, 416], [416, 448]
print("Following sections sorted with offset == address - section patch using offset is safe.")
# Following sections sorted by offset
create_dol("dol7.dol", [
    DolDescriptor(index=1,  offset=0,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=5,  offset=32,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=8,  offset=64, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=10, offset=96, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=11, offset=128, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=12, offset=160, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=13, offset=192, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=14, offset=224, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=15, offset=256, address=416, length=32, byte=b"\xE0")])
mappeurs_dict[7] = [
    [0, 32, 0],
    [32, 32, 96],
    [64, 32, 128],
    [96, 32, 224],
    [128, 32, 256],
    [160, 32, 288],
    [192, 32, 352],
    [224, 32, 384],
    [256, 32, 416]]

# Following sections reverse sorted by offset
create_dol("dol8.dol", [
    DolDescriptor(index=1, offset=256, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=5, offset=224, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=8, offset=192, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=10, offset=160, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=11, offset=128, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=12, offset=96, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=13,  offset=64, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=14,  offset=32,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=15,  offset=0,   address=0,   length=32, byte=b"\x10")])
mappeurs_dict[8] = [
    [256, 32, 416],
    [224, 32, 384],
    [192, 32, 352],
    [160, 32, 288],
    [128, 32, 256],
    [96, 32, 224],
    [64, 32, 128],
    [32, 32, 96],
    [0, 32, 0]]

# shuffled
# Following sections unsorted by offset
create_dol("dol9.dol", [
    DolDescriptor(index=1, offset=64, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=5, offset=0, address=0, length=32, byte=b"\x10"),
    DolDescriptor(index=8, offset=32, address=96, length=32, byte=b"\x40"),
    DolDescriptor(index=10, offset=224, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=11, offset=192, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=12, offset=96, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=13, offset=256, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=14, offset=160, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=15, offset=128, address=256, length=32, byte=b"\x90")])
mappeurs_dict[9] = [
    [64, 32, 128],
    [0, 32, 0],
    [32, 32, 96],
    [224, 32, 384],
    [192, 32, 352],
    [96, 32, 224],
    [256, 32, 416],
    [160, 32, 288],
    [128, 32, 256]]

# Sames as previously but with offset reverse sorted / shuffled / from addresses
# offset reverse sorted from address
create_dol("dol10.dol", [
    DolDescriptor(index=1,  offset=256,   address=0,   length=32, byte=b"\x10"),
    DolDescriptor(index=5,  offset=224,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=8,  offset=192, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=10, offset=160, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=11, offset=128, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=12, offset=96, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=13, offset=64, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=14, offset=32, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=15, offset=0, address=416, length=32, byte=b"\xE0")])
mappeurs_dict[10] = [
    [256, 32, 0],
    [224, 32, 96],
    [192, 32, 128],
    [160, 32, 224],
    [128, 32, 256],
    [96, 32, 288],
    [64, 32, 352],
    [32, 32, 384],
    [0, 32, 416]]

# offset reverse sorted from address / reversed
create_dol("dol11.dol", [
    DolDescriptor(index=1, offset=0, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=5, offset=32, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=8, offset=64, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=10, offset=96, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=11, offset=128, address=256, length=32, byte=b"\x90"),
    DolDescriptor(index=12, offset=160, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=13,  offset=192, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=14,  offset=224,  address=96,  length=32, byte=b"\x40"),
    DolDescriptor(index=15,  offset=256,   address=0,   length=32, byte=b"\x10")])
mappeurs_dict[11] = [
    [0, 32, 416],
    [32, 32, 384],
    [64, 32, 352],
    [96, 32, 288],
    [128, 32, 256],
    [160, 32, 224],
    [192, 32, 128],
    [224, 32, 96],
    [256, 32, 0]]

# offset shuffled from address
create_dol("dol12.dol", [
    DolDescriptor(index=1, offset=192, address=128, length=32, byte=b"\x50"),
    DolDescriptor(index=5, offset=224, address=0, length=32, byte=b"\x10"),
    DolDescriptor(index=8, offset=160, address=96, length=32, byte=b"\x40"),
    DolDescriptor(index=10, offset=64, address=384, length=32, byte=b"\xD0"),
    DolDescriptor(index=11, offset=0, address=352, length=32, byte=b"\xC0"),
    DolDescriptor(index=12, offset=32, address=224, length=32, byte=b"\x80"),
    DolDescriptor(index=13, offset=128, address=416, length=32, byte=b"\xE0"),
    DolDescriptor(index=14, offset=256, address=288, length=32, byte=b"\xA0"),
    DolDescriptor(index=15, offset=96, address=256, length=32, byte=b"\x90")])
mappeurs_dict[12] = [
    [192, 32, 128],
    [224, 32, 0],
    [160, 32, 96],
    [64, 32, 384],
    [0, 32, 352],
    [32, 32, 224],
    [128, 32, 416],
    [256, 32, 288],
    [96, 32, 256]]
    # Overlapping +3 sections matching right  # [126, 320]
# Middle   -1 + 1                         # [353, 383] \x55
intervals_list = []
# Sections: [0, 32], [96, 128], [128, 160], [224, 256], [256, 288], [288, 320], [352, 384], [384, 416], [416, 448]
# Beginning of dol file                   # [0, 24] \x11
# Matching right before empty             # [28, 32] \x22
# Matching left after empty               # [96, 100] \x33
# Overlapping +3 sections matching right  # [225, 383] \x55
# Middle                                  # [390, 394] \x66
# Endin map with overlap                  # [414, 448] \x77
# [[begin, end, byte], ...]
intervals_list.append([[0, 24, b"\x11"], [28, 32, b"\x22"], [96, 100, b"\x33"],
    [224, 320, b"\x44"], [225, 319, b"\x55"], [390, 394, b"\x66"], [414, 448, b"\x77"]])
intervals_list.append(sorted(intervals_list[0], key=lambda x: x, reverse=True))
intervals_list.append([[414, 448, b"\x77"], [353, 383, b"\x55"], [96, 100, b"\x33"], [390, 394, b"\x66"], [28, 32, b"\x22"], [224, 320, b"\x44"], [0, 24, b"\x11"]])

# Total file patch
intervals_list.append([[0, 32, b"\x11"], [96, 160, b"\x22"], [224, 320, b"\x33"], [352, 448, b"\x44"]])
intervals_list.append(sorted(intervals_list[1], key=lambda x: x, reverse=True))
intervals_list.append([[96, 160, b"\x22"], [0, 32, b"\x11"], [352, 448, b"\x44"], [224, 320, b"\x33"]])
# same but shuffled

test_dols(range(7,12), intervals_list)

print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
shutil.rmtree(ini_path)
shutil.rmtree(dol_tests_path)
shutil.rmtree(dols_save_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
