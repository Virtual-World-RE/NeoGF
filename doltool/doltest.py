from doltool import parse_action_replay_ini, InvalidIniFileEntryError, InvalidImgOffsetError, InvalidVirtualAddressError, Dol
import shutil
from pathlib import Path
from time import time

__version__ = "0.0.1"
__author__ = "algoflash"
__license__ = "MIT"
__status__ = "developpement"

##################################################
# Installation
##################################################
# Original "eu.dol" has to be placed in the folder.

test_path = Path("doltool_tests")

##################################################
# doltool.py commands wrappers
##################################################
def doltool_resolve_img2virtual(dol_path:Path, offset:int):
    if os.system(f"python doltool.py -i2v \"{dol_path}\" offset") != 0:
        raise Exception("Error while resolving dol offset to virtual address.")
def doltool_resolve_virtual2img(dol_path:Path, offset:int):
    if os.system(f"python doltool.py -i2v \"{dol_path}\" offset") != 0:
        raise Exception("Error while resolving virtual address to dol offset.")

"""
def doltool_stats(path):
    if os.system(f"python doltool.py -s \"{path}\" > NUL") != 0:
        raise Exception("Error while getting stats.")
"""

TEST_COUNT = 3

start = time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if test_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{test_path}")

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Testing valid action_replay_code parsing.")
print("###############################################################################")
test_path.mkdir()

valid_action_replay_ini = """[ActionReplay_Enabled]
$Costs
$HP
$B Ammo and Refill Codes
$B Mode and Reload Codes
$X Ammo and Refill Codes
$X Mode and Reload Codes
$Warehouse Full

[ActionReplay]
$Costs
022E2CC0 00050096
022E2CCC 00050136
022E2CD8 0005012C
022E2CE4 000500D2
042E4E2A 0000005A
042E4F92 000001E0
042E50FA 0000005A
042E5262 0001003C
042E53CA 00000078
042E5532 0000003C
042E569A 0000003C
042E5802 00000078
042E596A 0000000A
"""

(test_path / "test1.ini").write_text(valid_action_replay_ini)
valid_list = parse_action_replay_ini(test_path / "test1.ini")

expected_result = [
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
    (int("802E596A", 16), b"\x00\x00\x00\x0A")]

if valid_list != expected_result:
    raise Exception("Error - Invalid ini parsing.")
print("Valid parsing as Expected.")

invalid1_action_replay_ini = """
[]
.

122E2CC0 00050096
"""
invalid2_action_replay_ini = """
[]
.
a
082E2CC0 00050096
"""
invalid3_action_replay_ini = """
[]
.
a
082E2CC0 00050096
"""
invalid4_action_replay_ini = """
[]
.

082E2CC0  00050096
"""
for invalid_action_replay_ini in [invalid1_action_replay_ini, invalid2_action_replay_ini, invalid3_action_replay_ini, invalid4_action_replay_ini]:
    try:
        (test_path / "test.ini").write_text(invalid_action_replay_ini)
        valid_list = parse_action_replay_ini(test_path / "test.ini")
        raise Exception("Error - InvalidIniFileEntryError Exception should have been triggered.")
    except InvalidIniFileEntryError:
        print("Correct InvalidIniFileEntryError triggered.")

print("###############################################################################")
print(f"# TEST 2/{TEST_COUNT}")
print("# Testing valid dol.resolve_img2virtual conversion.")
print("###############################################################################")
# For EU dol:
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

print("Testing first offset of unalocated segments to raise Exception:")
for invalid_offset in [0x9f, 0x3bd400]:
    try:
        dol.resolve_img2virtual(invalid_offset)
        raise Exception("Error - InvalidImgOffsetError Exception should have been triggered.")
    except InvalidImgOffsetError:
        print("Correct InvalidImgOffsetError triggered.")

print("###############################################################################")
print(f"# TEST 3/{TEST_COUNT}")
print("# Testing valid dol.resolve_virtual2img conversion.")
print("###############################################################################")
# For EU dol:
print("Testing first virtual address of each segments with correct output:")
for (offset, virtual_address) in [(0x100, 0x80003100), (0x25e0, 0x800055e0), (0x2aede0, 0x802b1de0), (0x2aee00, 0x802b1e00), (0x2aee20, 0x802b1e20), (0x2bde80, 0x802c0e80), (0x3b3bc0, 0x8043cbe0), (0x3b66e0, 0x80440080)]:
    if dol.resolve_virtual2img(virtual_address) == offset:
        print("Correct translation")
    else:
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
print(f"# Cleaning test folders.")
print("###############################################################################")
# remove test_path
shutil.rmtree(test_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
