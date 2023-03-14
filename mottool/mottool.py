#!/usr/bin/env python3
from math import ceil
from pathlib import Path
import shutil
from struct import pack, unpack
from os import listdir
import logging
from enum import Enum
import re

__version__ = "0.0.17"
__author__ = "rigodron, algoflash, GGLinnk, CrystalPixel"
__license__ = "MIT"
__status__ = "developpement"

def extract_animations(mot_path: Path, dest_folder: Path):
    """
    Extract the animations from a mot file and write them to separate files
    """
    with open(mot_path, "rb") as mot_file:
        # Read the header with unpack (4 bytes) of 6 offsets (4 bytes each)
        header = unpack(">6I", mot_file.read(24))
        # All offsets represents list of another offsets (animations header)
        # Separate by 0xFFFFFFFF (end of each list)

        animation_index = 0
        
        for i in range(len(header) -1):
            mot_file.seek(header[i])
            animations_offsets = unpack(">" + "I" * ceil(header[i] / 4), mot_file.read(header[i]))
            
            for j in range(len(animations_offsets) - 1):
                if animations_offsets[j] == 0xFFFFFFFF:
                    break
                if animations_offsets[j] == 0x00000000:
                    continue
                
                mot_file.seek(animations_offsets[j])
                animation_header = unpack(">4I", mot_file.read(16))
                
                file_size, data_block_size, relocation_table_count, root_count = animation_header
                
                animation_data = mot_file.read(file_size - 16)
                
                dest_path = dest_folder / f"animation_{animation_index}.dat"
                with open(dest_path, "wb") as dest_file:
                    dest_file.write(pack(">4I", file_size, data_block_size, relocation_table_count, root_count) + animation_data)
                    dest_file.write(b"\x00" * (ceil(dest_file.tell() / 16) * 16 - dest_file.tell()))
                
                animation_index += 1


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='MOT unpacker - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-test', '--test', action='store_true', help="-test source_folder (dest_file.mot) : mot source_folder in new file source_folder.mot or dest_file if specified")
    return parser

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.test:
        logging.info("### Test ###")
        extract_animations(p_input, p_output)
