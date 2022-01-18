#!/usr/bin/env python3
import argparse
import hashlib
import os
from pathlib import Path
import pzztool
import shutil


__version__ = "0.0.2"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


unpack_path = Path("unpack")
repack_path = Path("repack")
# afsdump_path = Path("afs_data/root")


# compare all files sha256 from folder1 and folder2
#     -> print the filename if there is a difference
def verify_sha256(folder1: Path, folder2: Path):
    invalid_files_count = 0
    for pzz_path in folder1.glob("*.pzz"):
        if hashlib.sha256( pzz_path.read_bytes() ).hexdigest() != hashlib.sha256( (folder2 / pzz_path.name).read_bytes() ).hexdigest() :
            print(f"ERROR - INVALID FILE : {pzz_file_name}")
            invalid_files_count +=1
    print(f"Invalid files : {invalid_files_count}/{len(list(folder1.glob('*')))}")


def get_argparser():
    parser = argparse.ArgumentParser(description='TEST TOOL')
    parser.add_argument('input_path',  metavar='INPUT',  help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-tdc',  '--test-decompress-compress',   action='store_true', help="")
    group.add_argument('-tbup', '--test-batch-unpack-pack',     action='store_true', help="""
        -tbup source_pzz_folder
            source_pzz_folder  : put all pzz in this folder
            unpack_path : will be created with all unpacked pzz from pzz folder
            repack_path : will be created with all packed pzz from unpack_path folder
        print file_name when sha256 is different between source_pzz_folder and repack_path folder""")
    group.add_argument('-tbunpzzpzz', '--test-batch-unpzz-pzz', action='store_true', help="""
        -tbunpzzpzz source_pzz_folder
            source_pzz_folder  : put all pzz in this folder
            unpack_path : will be created with all unpzz pzz from pzz folder
            repack_path : will be created with all pzz(pzz_folder) from unpack_path folder
        print file_name when sha256 is different between source_pzz_folder and repack_path folder""")
    group.add_argument('-tcd', '--test-check-decompress',       action='store_true', help="""
        pzz : put all pzz in this folder
        then tip "pzztool.py -tcd pzz"
        The script will then check that tpls are correctly decompressed with their specific characteristics""")
    return parser


if __name__ == '__main__':

    if unpack_path.is_dir() or repack_path.is_dir():
        raise Exception(f"Error - Please remove:\n-{unpack_path}\n{repack_path}")
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)

    if args.test_decompress_compress:
        print("# TEST : DECOMPRESS COMPRESS")

        for pzzp_path in p_input.glob('*'):
            original_bytes = pzzp_path.read_bytes()
            recomp_bytes = pzztool.pzz_compress(pzztool.pzz_decompress(original_bytes))

            original_digest = hashlib.sha256(original_bytes).hexdigest()
            recomp_digest = hashlib.sha256(recomp_bytes).hexdigest()

            if original_digest != recomp_digest:
                print(f"Invalid sha256 for {pzzp_path} : ({original_digest}) ({recomp_digest})")
    elif args.test_batch_unpack_pack:
        print("# TEST : BATCH UNPACK PACK")
        # Remove unpack_path and repack_path
        if unpack_path.is_dir():
            shutil.rmtree(unpack_path)
        if repack_path.is_dir():
            shutil.rmtree(repack_path)

        if os.system(f"python pzztool.py -bu {p_input} {unpack_path}") != 0:
            raise Exception("Error while batch unpack.")
        if os.system(f"python pzztool.py -bp {unpack_path} {repack_path}") != 0:
            raise Exception("Error while batch pack.")
        verify_sha256(p_input, repack_path)
    elif args.test_batch_unpzz_pzz:
        # Remove unpack_path and repack_path
        if unpack_path.is_dir():
            shutil.rmtree(unpack_path)
        if repack_path.is_dir():
            shutil.rmtree(repack_path)

        if os.system(f"python pzztool.py -bunpzz {p_input} {unpack_path}") != 0:
            raise Exception("Error while batch unpzz.")
        if os.system(f"python pzztool.py -bpzz {unpack_path} {repack_path}") != 0:
            raise Exception("Error while batch pzz.")
        verify_sha256(p_input, repack_path)

        """
            if pzz : U -> decomp / already tested because unpzz let it decompressed by default
            if pzz : U -> comp   / has to be tested
            if pzz : C -> decomp / already tested because unpzz decompress by default
            if pzz : C -> comp   / has to be tested
        """
        # Remove repack_path
        shutil.rmtree(repack_path)
        
        # For all unpack_path folder we compress the file (if U -> comp ; if C -> comp)
        for pzzpart_path in unpack_path.glob('*/*'):
            # create a new compressed file without removing the original file
            if os.system(f"python pzztool.py -c {pzzpart_path}") != 0:
                raise Exception("Error while compress.")
            # remove the original
            os.remove(f"{pzzpart_path}")

        if os.system(f"python pzztool.py -bpzz {unpack_path} {repack_path}") != 0:
            raise Exception("Error while batch pzz.")
        verify_sha256(p_input, repack_path)
    elif args.test_check_decompress:
        print("# TEST : CHECK DECOMPRESS")
        if os.system(f"python pzztool.py -bunpzz {p_input} {unpack_path}") != 0:
            raise Exception("Error while batch unpzz.")

        invalid_files_count = 0
        total = 0
        # check that all TPLs length is a multiple of 32
        for tpl_path in unpack_path.glob("**/*.tpl"):
            if p.is_file():
                total+=1
                if (tpl_path.stat().st_size % 32) != 0:
                    print(f"Invalid TPL file length modulo 32 ({tpl_path.stat().st_size % 32}) - {tpl_path}")
                    invalid_files_count += 1
        print(f"Invalid files : {invalid_files_count}/{total}")
