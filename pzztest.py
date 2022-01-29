#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
from time import time


__version__ = "0.0.6"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


##################################################
# Set afsdump_path with your dumped afs_data.afs
##################################################
afsdump_path = Path("afs_data/root")

# Created tmp paths
pzzfolder_path = Path("pzz")
unpack_path = Path("unpack")
repack_path = Path("repack")
compress_path = Path("compress")
batchcompress_path = Path("batch_compress")
batchdecompress_path = Path("batch_decompress")


def test_storage():
    total, used, free = shutil.disk_usage("/")
    if free - 10**10 < 6 * sum(path.stat().st_size for path in afsdump_path.glob('*.pzz') if path.is_file()):
        raise Exception("Error - Not enought free space on the disk to run tests.")


# compare two files
def compare_files(file1_path:Path, file2_path:Path):
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


# compare all files from folder1 and folder2
#     -> raise an exception if there is a difference
def compare_folders(folder1: Path, folder2: Path):
    folder1_paths = list(folder1.glob("*"))
    folder1_file_count = len(folder1_paths)
    print(f"compare \"{folder1}\" - \"{folder2}\" ({folder1_file_count} files)")
    if folder1_file_count == 0:
        raise Exception(f"Error - Empty folder: {folder1}")
    for file_path in folder1_paths:
        if not compare_files(file_path, (folder2 / file_path.name)):
            raise Exception(f"Error - Invalid file: {folder2 / file_path.name}")


##################################################
# pzztool.py commands wrappers
##################################################
def pzztool_bu(in_pzzfolder_path:Path, batchunpack_path:Path):
    if os.system(f"python pzztool.py -bu \"{in_pzzfolder_path}\" \"{batchunpack_path}\"") != 0:
        raise Exception("Error while batch unpack.")
def pzztool_bp(in_unpack_path:Path, batchpack_path:Path):
    if os.system(f"python pzztool.py -bp \"{in_unpack_path}\" \"{batchpack_path}\"") != 0:
        raise Exception("Error while batch pack.")
def pzztool_d(pzzp_path:Path, file_path:Path):
    if os.system(f"python pzztool.py -d \"{pzzp_path}\" \"{file_path}\"") != 0:
        raise Exception("Error while decompress.")
def pzztool_c(file_path:Path):
    if os.system(f"python pzztool.py -c \"{file_path}\"") != 0:
        raise Exception("Error while compress.")
def pzztool_bd(folder_path:Path, out_folder_path:Path):
    if os.system(f"python pzztool.py -bd \"{folder_path}\" \"{out_folder_path}\"") != 0:
        raise Exception("Error while batch decompress.")
def pzztool_bc(folder_path:Path, out_folder_path:Path):
    if os.system(f"python pzztool.py -bc \"{folder_path}\" \"{out_folder_path}\"") != 0:
        raise Exception("Error while batch compress.")
def pzztool_bunpzz(in_pzzfolder_path:Path, unpzzfolder_path:Path):
    if os.system(f"python pzztool.py -bunpzz \"{in_pzzfolder_path}\" \"{unpzzfolder_path}\"") != 0:
        raise Exception("Error while batch unpzz.")
def pzztool_bpzz(folder_path:Path, out_pzzfolder_path:Path):
    if os.system(f"python pzztool.py -bpzz \"{folder_path}\" \"{out_pzzfolder_path}\"") != 0:
        raise Exception("Error while batch pzz.")


TEST_COUNT = 5

start = time()
print("###############################################################################")
print("# Checking tests folder -> tests take 3 hour 35 minutes")
print("###############################################################################")
# Check if tests folders exist
if unpack_path.is_dir() or repack_path.is_dir() or compress_path.is_dir() or pzzfolder_path.is_dir() or batchdecompress_path.is_dir() or batchcompress_path.is_dir():
    raise Exception(f"Error - Please remove:\n-{unpack_path}\n-{repack_path}\n-{compress_path}\n-{pzzfolder_path}\n-{batchdecompress_path}\n-{batchcompress_path}")

test_storage()

print("###############################################################################")
print(f"# TEST 1/{TEST_COUNT}")
print("# Comparing [original pzz]->unpacked->repacked->[repack_path]")
print("###############################################################################")
pzzfolder_path.mkdir()
unpack_path.mkdir()
repack_path.mkdir()

for pzz_path in afsdump_path.glob("*.pzz"):
    shutil.copy(pzz_path, pzzfolder_path / pzz_path.name)

pzztool_bu(pzzfolder_path, unpack_path)
pzztool_bp(unpack_path, repack_path)

compare_folders(pzzfolder_path, repack_path)

shutil.rmtree(repack_path)

print("###############################################################################")
print(f"# TEST 2/{TEST_COUNT}")
print("# Comparing unpack_path/[*.pzzp]->decompress->compress_path/[*.pzzp] PZZ part")
print("###############################################################################")
compress_path.mkdir()
unpack_paths = list(unpack_path.glob("*/*.pzzp"))

for folder_path in unpack_path.glob("*"):
    (compress_path / folder_path.name).mkdir()

for pzzp_path in unpack_paths:
    pzztool_d(pzzp_path, compress_path / pzzp_path.parent.name / Path(pzzp_path.stem).with_suffix('.dat'))

for file_path in compress_path.glob('*/*'):
    pzztool_c(file_path)
    file_path.unlink()

for pzzp_path in unpack_paths:
    file_path = compress_path / pzzp_path.parent.name / pzzp_path.name
    print(f"compare \"{pzzp_path}\" - \"{file_path}\"")
    if not compare_files(pzzp_path, file_path):
        raise Exception(f"Invalid file: {file_path}")

print("###############################################################################")
print(f"# TEST 3/{TEST_COUNT}")
print("# Comparing [compress/*]->batch-decompress->batch-compress->[batchcompress_path]")
print("###############################################################################")
batchdecompress_path.mkdir()
batchcompress_path.mkdir()

compress_paths = list(compress_path.glob('*'))
for folder_path in compress_paths:
    pzztool_bd(folder_path, batchdecompress_path / folder_path.name)

for folder_path in batchdecompress_path.glob('*'):
    pzztool_bc(folder_path, batchcompress_path / folder_path.name)

# Copy uncompressed files that haven't been processed by *.pzzp glob
for file_path in unpack_path.glob('*/[0-9][0-9][0-9]U*'):
    shutil.copy(file_path, batchcompress_path / file_path.parent.name / file_path.name)

shutil.rmtree(unpack_path)
shutil.rmtree(batchdecompress_path)

for folder_path in compress_paths:
    compare_folders(compress_path / folder_path.name, batchcompress_path / folder_path.name)

shutil.rmtree(compress_path)
shutil.rmtree(batchcompress_path)

print("###############################################################################")
print(f"# TEST 4/{TEST_COUNT}")
print("# Comparing [pzzfolder_path]->batch-unpzz->batch-pzz->[repacked_path]")
print("###############################################################################")
pzztool_bunpzz(pzzfolder_path, unpack_path)
pzztool_bpzz(unpack_path, repack_path)

compare_folders(pzzfolder_path, repack_path)

shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

print("###############################################################################")
print(f"# TEST 5/{TEST_COUNT}")
print("# Comparing [pzzfolder_path]->batch-unpack->(decompress or compress)->\nbatch-pzz->[repacked_path]")
print("###############################################################################")
# if pzz: U -> decomp / already tested because unpzz let it decompressed by default
# if pzz: U -> comp   / has to be tested
# if pzz: C -> decomp / already tested because unpzz decompress by default
# if pzz: C -> comp   / has to be tested
unpack_path.mkdir()
repack_path.mkdir()

pzztool_bu(pzzfolder_path, unpack_path)

# For all unpack_path folder we compress the file (if U -> comp ; if C -> comp)
for file_path in unpack_path.glob('*/*'):
    if file_path.suffix != ".pzzp":
        # create a new compressed file without removing the original file
        pzztool_c(file_path)
        # remove the original
        file_path.unlink()

pzztool_bpzz(unpack_path, repack_path)

compare_folders(pzzfolder_path, repack_path)

# Remove tests folders
print("###############################################################################")
print(f"# Cleaning test folders.")
print("###############################################################################")
shutil.rmtree(pzzfolder_path)
shutil.rmtree(unpack_path)
shutil.rmtree(repack_path)

end = time()
print("###############################################################################")
print(f"# All tests are OK - elapsed time: {end - start}")
print("###############################################################################")
