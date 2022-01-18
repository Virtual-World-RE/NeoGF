#!/usr/bin/env python3
import argparse
from pathlib import Path


__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"
__license__ = "MIT"
__status__ = "developpement"


def get_argparser():
    parser = argparse.ArgumentParser(description='Test tool - Proof Of Concept')
    parser.add_argument('input_path',  metavar='INPUT',  help='')

    group.add_argument('-tcp', '--test-compare-position',   action='store_true', help="compare plxxxx.pzz subfiles with plxxxx files inside unpacked afs_data")
    return parser


if __name__ == '__main__':
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)

    if args.test_compare_position:
        # FULL_AFS_FILE_DUMP contains all unpacked files from afs_data.afs
        # unpack_path contains result of pzztool.py -bunpzz on all pzz files
        # What you have to compare (prove that files of borgs (plxxxx.pzz) are positional and same as pl files in the root of afs_data) :
        # pzztest.py -tcp 0 data.bin
        #     Some afs_data files are named data2 or data3 and it's sometime absent
        # pzztest.py -tcp 2 hit.bin
        # pzztest.py -tcp 3 mot.bin
        # pzztest.py -tcp 4 _mdl.arc
        # pzztest.py -tcp 5 b_mdl.arc
        # pzztest.py -tcp 6 g_mdl.arc
        # pzztest.py -tcp 7 s_mdl.arc
        # pzztest.py -tcp 8 c_mdl.arc
        # pzztest.py -tcp 9 k_mdl.arc

        for pzzpart_path in unpack_path.glob(f"**/00{p_input}*"):
            file_path = afsdump_path / pzzpart_path.parent.name / p_output

            if pzzpart_path.parent.name[:2] == "pl":
                if not file_path.is_file():
                    print(f"File doesn't exist : {file_path}")
                elif pzzpart_path.stat().st_size == 0:
                    print(f"File is empty : {pzzpart_path}")
                else:
                    if not verify_sha256_2(pzzpart_path, file_path):
                        print(f"DIFFERENCE : {pzzpart_path} - {file_path}")
