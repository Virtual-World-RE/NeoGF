#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path
import shutil
import time


__version__ = "0.0.3"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"

pzzfolder_path = Path("pzz")
unpack_path = Path("unpack")
repack_path = Path("repack")
compress_path = Path("compress")
batchcompress_path = Path("batch_compress")
batchdecompress_path = Path("batch_decompress")
afsdump_path = Path("afs_data/root")


# compare two files sha256
def compare_sha256(file1_path:Path, file2_path:Path):
    return hashlib.sha256( file1_path.read_bytes() ).hexdigest() == hashlib.sha256( file2_path.read_bytes() ).hexdigest()

# compare all files sha256 from folder1 and folder2
#     -> raise an exception if there is a difference
def verify_sha256(folder1: Path, folder2: Path):
    print(f"compare \"{folder1}\" - \"{folder2}\"")
    for file_path in folder1.glob("*"):
        if hashlib.sha256( file_path.read_bytes() ).hexdigest() != hashlib.sha256( (folder2 / file_path.name).read_bytes() ).hexdigest() :
            raise Exception(f"ERROR - INVALID FILE : {folder2 / file_path.name}")


start = time.time()
print("###############################################################################")
print("# Checking tests folder")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or repack_path.is_dir() or compress_path.is_dir() or pzzfolder_path.is_dir() or batchdecompress_path.is_dir() or batchcompress_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{repack_path}\n-{compress_path}\n-{pzzfolder_path}\n-{batchdecompress_path}\n-{batchcompress_path}")

print("###############################################################################")
print("# TEST 1/5")
print("# Comparing [original pzz]->unpacked->repacked->[repack_path]")
print("###############################################################################")
pzzfolder_path.mkdir()
unpack_path.mkdir()
repack_path.mkdir()

for pzz_path in afsdump_path.glob("*.pzz"):
    shutil.copy(pzz_path, pzzfolder_path / pzz_path.name)

if os.system(f"python pzztool.py -bu \"{pzzfolder_path}\" \"{unpack_path}\"") != 0:
    raise Exception("Error while batch unpack.")
if os.system(f"python pzztool.py -bp \"{unpack_path}\" \"{repack_path}\"") != 0:
    raise Exception("Error while batch pack.")

for pzz_path in pzzfolder_path.glob("*"):
    print(f"compare \"{pzz_path}\" - \"{repack_path / pzz_path.name}\"")
    if not compare_sha256(pzz_path, repack_path / pzz_path.name):
        raise Exception(f"INVALID FILE: {repack_path / pzz_path.name}")

shutil.rmtree(repack_path)

print("###############################################################################")
print("# TEST 2/5")
print("# Comparing unpack_path/[*.pzzp]->decompress->compress_path/[*.pzzp] PZZ part")
print("###############################################################################")
compress_path.mkdir()

for folder_path in unpack_path.glob("*"):
    (compress_path / folder_path.name).mkdir()

for pzzp_path in unpack_path.glob("*/*.pzzp"):
    if os.system(f"python pzztool.py -d \"{pzzp_path}\" \"{compress_path / pzzp_path.parent.name / Path(pzzp_path.stem).with_suffix('.dat')}\"") != 0:
        raise Exception("Error while decompress.")

for file_path in compress_path.glob('*/*'):
    if os.system(f"python pzztool.py -c \"{file_path}\"") != 0:
        raise Exception("Error while compress.")
    file_path.unlink()

for pzzp_path in unpack_path.glob("*/*.pzzp"):
    file_path = compress_path / pzzp_path.parent.name / pzzp_path.name
    print(f"compare \"{pzzp_path}\" - \"{file_path}\"")
    if not compare_sha256(pzzp_path, file_path):
        raise Exception(f"INVALID FILE: {file_path}")

print("###############################################################################")
print("# TEST 3/5")
print("# Comparing [compress/*]->batch-decompress->batch-compress->[batchcompress_path]")
print("###############################################################################")
batchdecompress_path.mkdir()
batchcompress_path.mkdir()

for folder_path in compress_path.glob('*'):
    if os.system(f"python pzztool.py -bd \"{folder_path}\" \"{batchdecompress_path / folder_path.name}\"") != 0:
        raise Exception("Error while decompress.")

for folder_path in batchdecompress_path.glob('*'):
    if os.system(f"python pzztool.py -bc \"{folder_path}\" \"{batchcompress_path / folder_path.name}\"") != 0:
        raise Exception("Error while decompress.")

for file_path in unpack_path.glob('*/[0-9][0-9][0-9]U*'):
    shutil.copy(file_path, batchcompress_path / file_path.parent.name / file_path.name)

shutil.rmtree(unpack_path)
shutil.rmtree(batchdecompress_path)

for folder_path in compress_path.glob("*"):
    verify_sha256(compress_path / folder_path.name, batchcompress_path / folder_path.name)
shutil.rmtree(batchcompress_path)

print("###############################################################################")
print("# TEST 4/5")
print("# Comparing [pzzfolder_path]->batch-unpzz->batch-pzz->[repacked_path]")
print("###############################################################################")
if os.system(f"python pzztool.py -bunpzz \"{pzzfolder_path}\" \"{unpack_path}\"") != 0:
    raise Exception("Error while batch unpzz.")
if os.system(f"python pzztool.py -bpzz \"{unpack_path}\" \"{repack_path}\"") != 0:
    raise Exception("Error while batch pzz.")

verify_sha256(pzzfolder_path, repack_path)
shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

print("###############################################################################")
print("# TEST 5/5")
print("# Comparing [pzzfolder_path]->batch-unpack->(decompress or compress)->\nbatch-pzz->[repacked_path]")
print("###############################################################################")
# if pzz : U -> decomp / already tested because unpzz let it decompressed by default
# if pzz : U -> comp   / has to be tested
# if pzz : C -> decomp / already tested because unpzz decompress by default
# if pzz : C -> comp   / has to be tested
unpack_path.mkdir()
repack_path.mkdir()

if os.system(f"python pzztool.py -bu \"{pzzfolder_path}\" \"{unpack_path}\"") != 0:
    raise Exception("Error while batch unpack.")

# For all unpack_path folder we compress the file (if U -> comp ; if C -> comp)
for file_path in unpack_path.glob('*/*'):
    if file_path.suffix != ".pzzp":
        # create a new compressed file without removing the original file
        if os.system(f"python pzztool.py -c \"{file_path}\"") != 0:
            raise Exception("Error while compress.")
        # remove the original
        file_path.unlink()

if os.system(f"python pzztool.py -bpzz \"{unpack_path}\" \"{repack_path}\"") != 0:
    raise Exception("Error while batch pzz.")

verify_sha256(pzzfolder_path, repack_path)

# Remove tests folders
print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
shutil.rmtree(pzzfolder_path)
shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

end = time.time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time : {end - start}")
print("###############################################################################")
