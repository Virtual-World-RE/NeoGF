#!/usr/bin/env python3
from configparser import ConfigParser
import logging
from pathlib import Path


__version__ = "0.0.19"
__author__ = "rigodron, algoflash, GGLinnk, CrystalPixel"
__license__ = "MIT"
__status__ = "developpement"


def align(offset:int, align:int):
    """
    Give the upper rounded offset aligned using the align value.
    input: offset = int
    input: align = int
    return offset = int
    """
    if offset % align == 0: return offset
    return offset + align - (offset % align)


class MotFile:
    "Unpack and pack motions in the motFile."
    __groups_offsets = None
    __GROUPS_HEADER_LEN = 0x40
    __TOTAL_HEADER_ALIGN = 0x20
    __MOTION_FILE_ALIGN = 0x20
    def unpack(self, motfile_path:Path, folder_path:Path):
        ""
        logging.info(f"Unpacking {motfile_path} in {folder_path}...")
        
        with motfile_path.open("rb") as motfile_file:
            self.__groups_offsets = []

            for _ in range(self.__GROUPS_HEADER_LEN // 4):
                group_offset = int.from_bytes(motfile_file.read(4), "big")
                self.__groups_offsets.append(group_offset)

            folder_path.mkdir(parents=True)
            logging.debug(f"Total of groups: {len(self.__groups_offsets):02}")
            for group_index, group_offset in enumerate(self.__groups_offsets):
                if group_offset == 0:
                    continue
                group_path = folder_path / f"{group_index:02}"
                group_path.mkdir()

                motions_offsets = []
                motfile_file.seek(group_offset)

                last_motion_offset = int.from_bytes(motfile_file.read(4), "big")
                while last_motion_offset != -1:
                    motions_offsets.append(last_motion_offset)
                    last_motion_offset = int.from_bytes(motfile_file.read(4), "big", signed=True)

                for motion_index, motion_offset in enumerate(motions_offsets):
                    logging.debug(f"[unpacking] group: {group_index:02} motion: {motion_index:04}")

                    new_motion_path = (group_path / f"{motion_index:04}").with_suffix(".mot")
                    if motion_offset == 0:
                        # We create an empty file.
                        new_motion_path.touch()
                        continue

                    motfile_file.seek(motion_offset)
                    motionfile_len = int.from_bytes(motfile_file.read(4), "big")

                    motfile_file.seek(motion_offset)
                    new_motion_path.write_bytes( motfile_file.read(motionfile_len) )
    def pack(self, folder_path:Path, motfile_path:Path):
        ""
        logging.info(f"Packing {folder_path} in {motfile_path}...")

        groups_count = int(list(folder_path.glob("*"))[-1].name) + 1
        group_motion_len_list = [[]] * groups_count

        for group_index in range(groups_count):
            if not (folder_path / f"{group_index:02}").is_dir():
                continue
            motions_count = len(list((folder_path / f"{group_index:02}").glob("*")))
            if motions_count == 0:
                continue
            group_motion_len_list[group_index] = [None] * motions_count

            for motion_index in range(motions_count):
                group_motion_len_list[group_index][motion_index] = (folder_path / f"{group_index:02}" / f"{motion_index:04}").with_suffix(".mot").stat().st_size
                logging.debug(f"group: {group_index:02} motion: {motion_index:04} len: {group_motion_len_list[group_index][motion_index]:08x}")

        current_offset = self.__GROUPS_HEADER_LEN
        motfile_headers_data = b""

        for group_index, group in enumerate(group_motion_len_list):
            if len(group) == 0:
                motfile_headers_data += b"\x00\x00\x00\x00"
                continue
            motfile_headers_data += current_offset.to_bytes(4, "big")
            current_offset += len(group_motion_len_list[group_index]) * 4 + 4
        
        current_offset = align(current_offset, self.__TOTAL_HEADER_ALIGN)

        motfile_headers_data += b"\x00" * (self.__GROUPS_HEADER_LEN - len(motfile_headers_data))

        # current_offset point now to the first file position and motfile_headers_data contains groups header data
        with motfile_path.open("wb") as motfile_file:
            for group_index, group in enumerate(group_motion_len_list):
                if len(group) == 0:
                    continue
                group_header_data = b""
                for motion_index, motion_len in enumerate(group):
                    if motion_len == 0:
                        group_header_data += b"\x00\x00\x00\x00"
                        continue
                    group_header_data += current_offset.to_bytes(4, "big")

                    motfile_file.seek(current_offset)
                    motfile_file.write((folder_path / f"{group_index:02}" / f"{motion_index:04}").with_suffix(".mot").read_bytes())

                    current_offset += align(motion_len, self.__MOTION_FILE_ALIGN)
                motfile_headers_data += group_header_data + b"\xff\xff\xff\xff"

            motfile_headers_data += b"\x00" * (align(len(motfile_headers_data), self.__TOTAL_HEADER_ALIGN) - len(motfile_headers_data))

            # current_offset = motfile_len
            motfile_file.seek(0)
            motfile_file.write(motfile_headers_data)
            motfile_file.seek(current_offset - 1)
            motfile_file.write(b"\x00")


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='Gotcha Force MOT packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-c', '--charset', type=str, help='-c=USA: use USA charset when unpacking.', default="")
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack', action='store_true', help="-p source_folder (dest_file.bin): Pack source_folder in new file source_folder.bin or dest_file.bin if specified.")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_file.bin (dest_folder): Unpack the motFile file in new folder source_file or dest_folder if specified.")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    motFile = MotFile()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        logging.info("### Pack")
        if not p_input.is_dir():
            raise Exception("Error - Invalid unpacked motFile folder path.")

        if p_output == Path("."):
            p_output = p_input.with_suffix(".bin")

        if p_output.is_file() or p_output.is_dir():
            raise Exception(f"Error - {p_output} already exist. Please remove it before packing.")

        motFile.pack(p_input, p_output)
    elif args.unpack:
        logging.info("### Unpack")
        if not p_input.is_file():
            raise Exception("Error - Invalid motFile file path.")

        if p_output == Path("."):
            p_output = p_input.parent / p_input.stem

        if p_output.is_file() or p_output.is_dir():
            raise Exception(f"Error - {p_output} already exist. Please remove it before unpacking.")

        motFile.unpack(p_input, p_output)
