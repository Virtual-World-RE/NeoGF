#!/usr/bin/env python3
from math import ceil
from pathlib import Path
import shutil
import logging

__version__ = "0.14.7"
__author__ = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"
__license__ = "MIT"
__status__ = "developpement"


# For more information on the PZZ file format :
# http://virtualre.rf.gd/index.php/PZZ_(Gotcha_Force)


BIT_COMPRESSION_FLAG = 0x40000000
FILE_LENGTH_MASK = 0x3FFFFFFF
BLOCK_SIZE = 0x800
TPL_MAGIC_NUMBER = b"\x00\x20\xAF\x30" # http://virtualre.rf.gd/index.php/TPL_(Format_de_fichier)
CHD_MAGIC_NUMBER = b"Head"
BINHITS_MAGIC_NUMBER = b"STIH"
TSB_MAGIC_NUMBER = b"TSBD"
ICON_MAGIC_NUMBER = b"GOTCHA FORCE"


def get_file_path(file_data: bytes, path: Path):
    # If it's a plxxxx or a dpxxxx.pzz
    # 001 is always absent for dpxxxx
    if path.name[5:7] == "pl" or path.name[5:7] == "dp":
        if path.name[0:3] == "000":
            return path.with_name(path.name + "data").with_suffix(".bin")
        if path.name[0:3] == "002":
            return path.with_name(path.name + "hit").with_suffix(".bin")
        if path.name[0:3] == "003":
            return path.with_name(path.name + "mot").with_suffix(".bin")
        if path.name[0:3] == "004":
            return path.with_name(path.name + "_mdl").with_suffix(".arc")
        if path.name[0:3] == "005":
            return path.with_name(path.name + "b_mdl").with_suffix(".arc")
        if path.name[0:3] == "006":
            return path.with_name(path.name + "g_mdl").with_suffix(".arc")
        if path.name[0:3] == "007":
            return path.with_name(path.name + "s_mdl").with_suffix(".arc")
        if path.name[0:3] == "008":
            return path.with_name(path.name + "c_mdl").with_suffix(".arc")
        if path.name[0:3] == "009":
            return path.with_name(path.name + "k_mdl").with_suffix(".arc")
    elif path.name[5:9] == "efct":
        if path.name[0:3] == "001":
            return path.with_name(path.name + "00_mdl").with_suffix(".arc")
        if path.name[0:3] == "002":
            return path.with_name(path.name + "01_mdl").with_suffix(".arc")
    elif file_data.startswith(ICON_MAGIC_NUMBER):
        return path.with_name(path.name + "icon").with_suffix(".bin")
    if file_data.startswith(TPL_MAGIC_NUMBER):
        return path.with_suffix(".tpl")
    if file_data.startswith(CHD_MAGIC_NUMBER):
        return path.with_suffix(".chd")
    if file_data.startswith(TSB_MAGIC_NUMBER):
        return path.with_suffix(".tsb")
    if file_data.startswith(BINHITS_MAGIC_NUMBER):
        return path.with_suffix(".bin")
    # Default value
    return path.with_suffix(".dat")


# Not implemented : remove pad at the end of unpacked files
# The problem is that we can't know the exact initial Null bytes pad of the file.
# -> So we can't remove the trailing pad
def remove_padding(file_data: bytearray):
    return file_data
    # return file_data.rstrip(b'\x00')


def block_align(bout: bytes):
    # As demonstrated by pl080d/006C_pl080d.pzzp, we ad BLOCK_SIZE if it's aligned on a multiple of BLOCK_SIZE
    if len(bout) % BLOCK_SIZE == 0:
        return bout.ljust(BLOCK_SIZE * int(len(bout) / BLOCK_SIZE + 1), b"\x00")
    return bout.ljust(BLOCK_SIZE * ceil(len(bout) / BLOCK_SIZE), b"\x00")


def fix_pad_decompress(bout: bytes, path: Path):
    # We ajust file_len according to the file format after decompress
    if  path.name[5:7] == "pl" and path.suffix == ".arc" or \
        path.name[5:7] == "dp" and path.suffix == ".arc" or \
        path.name[5:9] == "efct" and path.suffix == ".arc":
        return bout[:-1]
    return bout


def pzz_decompress(compressed_bytes: bytes):
    uncompressed_bytes = bytearray()
    compressed_bytes_size = len(compressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = -1 # We rotate from 15 to 0 for compress flag
    i = 0
    while i < compressed_bytes_size:
        if cb_bit < 0:
            cb = compressed_bytes[i + 1]
            cb |= compressed_bytes[i + 0] << 8
            cb_bit = 15
            i += 2
            continue

        compress_flag = cb & (1 << cb_bit)
        cb_bit -= 1

        if compress_flag:
            c = compressed_bytes[i + 1]
            c |= compressed_bytes[i + 0] << 8

            offset = (c & 0x7FF) * 2
            if offset == 0:
                break  # End of the compressed data
            count = (c >> 11) * 2
            if count == 0:
                i += 2
                c = compressed_bytes[i + 1]
                c |= compressed_bytes[i + 0] << 8
                count = c * 2

            index = len(uncompressed_bytes) - offset
            for j in range(count):
                uncompressed_bytes.append(uncompressed_bytes[index + j]) # aaa a améliorer avec un slice
        else:
            uncompressed_bytes += compressed_bytes[i: i+2]
        i += 2

    return uncompressed_bytes


def pzz_compress(uncompressed_bytes: bytes):
    uncompressed_bytes += b"\x00" # # Adding pad doesn't change the result of compress
    compressed_bytes = bytearray(2)
    uncompressed_bytes_len = len(uncompressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = 15 # We rotate from 15 to 0 for compress flag
    cb_pos = 0

    i = 0
    while i < uncompressed_bytes_len:
        start = max(i - 4094, 0) # start = 2 if i = 4096 (BLOCK_SIZE*2)
        count_r = 0
        max_i = -1

        #######################################################
        # start : contains index .. (analysis of the algorithm is not redacted yet)
        #######################################################
        while True:
            # start = index first occurencie of uncompressed_bytes[i:i+2] between start and i+1
            #     We look in the 4094 last bytes
            start = uncompressed_bytes.find(uncompressed_bytes[i: i+2], start, i+1)

            # if the current 2 bytes aren't in the 4094 last bytes
            if start == -1:
                break

            # If the first occurencie isn't an index multiple of 2, we ignore it
            if start % 2 != 0:
                start += 1
                continue
            count = 2
            while   i < uncompressed_bytes_len - count and \
                    count < 0xFFFF * 2  and \
                    uncompressed_bytes[start+count]   == uncompressed_bytes[i+count] and \
                    uncompressed_bytes[start+count+1] == uncompressed_bytes[i+count+1]:
                count += 2
            if count_r < count:
                count_r = count
                max_i = start
            start += 2
        start = max_i

        compress_flag = 0
        if count_r >= 4:
            compress_flag = 1
            offset = (i - start) // 2
            count_r //= 2
            c = offset
            if count_r <= 0x1F:
                c |= count_r << 11
                compressed_bytes += c.to_bytes(2, "big")
            else:
                compressed_bytes += c.to_bytes(2, "big") + count_r.to_bytes(2, "big")
            i += count_r * 2
        else:
            compressed_bytes += uncompressed_bytes[i: i+2]
            i += 2
        cb |= (compress_flag << cb_bit)
        cb_bit -= 1
        if cb_bit < 0:
            compressed_bytes[cb_pos:cb_pos + 2] = cb.to_bytes(2, "big")
            cb = 0
            cb_bit = 15
            cb_pos = len(compressed_bytes)
            compressed_bytes += b"\x00\x00"

    cb |= (1 << cb_bit)
    compressed_bytes[cb_pos:cb_pos + 2] = cb.to_bytes(2, "big")
    compressed_bytes += b"\x00\x00"

    return block_align(compressed_bytes)


def pzz_unpack(pzz_path:Path, folder_path:Path, auto_decompress:bool = False):
    if pzz_path.suffix != ".pzz" and  pzz_path.suffix != ".mdt":
        logging.warning(f"Invalid file format '{pzz_path.suffix}'; it should be .pzz or .mdt file format")

    if folder_path != Path('.'):
        unpacked_pzz_path = folder_path
    else:
        unpacked_pzz_path = pzz_path.parent / pzz_path.stem

    if auto_decompress:
        logging.info(f"    unpzz({pzz_path}) in folder {unpacked_pzz_path}")
    else:
        logging.info(f"    unpacking {pzz_path} in folder {unpacked_pzz_path}")
    unpacked_pzz_path.mkdir(exist_ok=True)

    with pzz_path.open("rb") as pzz_file:
        file_count = int.from_bytes(pzz_file.read(4), "big")
        logging.debug(f"    -> File count : {file_count}")

        # get a list with header file descriptors
        files_descriptors_data = pzz_file.read(file_count * 4)
        files_descriptors = [int.from_bytes(files_descriptors_data[i:i+4], "big") for i in range(0, file_count*4, 4)]

        file_offset = BLOCK_SIZE
        for index, file_descriptor in enumerate(files_descriptors):
            # bit 30 is the compression flag (bits from 0 to 31)
            if file_descriptor & BIT_COMPRESSION_FLAG == 0:
                compression_status = 'U' # For the extracted filename: initialy not compressed
            else:
                compression_status = 'C' # For the extracted filename: initialy compressed (file will have ".pzzp" extension)

            # We keep the 30 first bits in file_descriptor (file_len / BLOCK_SIZE)
            file_descriptor &= FILE_LENGTH_MASK

            # file_len is padded according to BLOCK_SIZE
            file_len = file_descriptor * BLOCK_SIZE

            # We generate file name
            filename = f"{index:03}{compression_status}_{pzz_path.stem}"
            file_path = unpacked_pzz_path / filename

            logging.debug(f"    -> Offset: {file_offset:010} - {file_path}")

            # If file_len is Null we create an empty file and we pass to the next file_descriptor
            if file_len == 0:
                file_path.with_suffix(".dat").touch()
                continue

            # We seek at the file_offset
            pzz_file.seek(file_offset)

            # We extract the file and if auto_decompress is set we decompress all files
            file_data = pzz_file.read(file_len)
            if auto_decompress and compression_status == 'C':
                file_data = pzz_decompress(file_data)
            file_data = remove_padding(bytearray(file_data))

            if not auto_decompress and compression_status == 'C':
                file_path = file_path.with_suffix(".pzzp")
            else:
                file_path = get_file_path(file_data, file_path)

            file_path.write_bytes(fix_pad_decompress(file_data, file_path))

            # next file_offset = file_offset + file_len
            # File_len is aligned to BLOCK_SIZE with Null bytes
            file_offset += file_len


def pzz_pack(folder_path:Path, pzz_path:Path, auto_compress:bool = False):
    if pzz_path == Path('.'):
        pzz_path = folder_path.with_suffix(".pzz")
    if pzz_path.suffix != ".pzz" and pzz_path.suffix != ".mdt":
        logging.warning(f"Invalid file format '{pzz_path.suffix}' : dest must be a pzz or mdt")

    # We get all filenames from the folder to pzz
    files_path = list(folder_path.glob("*"))

    if auto_compress:
        logging.info(f"    pzz({folder_path}) in pzz {pzz_path}")
    else:
        logging.info(f"    packing({folder_path}) in pzz {pzz_path}")
    logging.debug(f"    -> {len(files_path)} files to pack")

    with pzz_path.open("wb") as pzz_file:
        # We seek to the end of the header
        pzz_file.seek(BLOCK_SIZE)

        # We get total files count to put it at the begining of the pzz header
        header_bytes = len(files_path).to_bytes(4, byteorder='big')

        # We write every files at the end of the pzz_file
        for file_path in files_path:
            is_compressed = file_path.suffix == ".pzzp"
            compression_status = file_path.name[3:4]

            file_data = file_path.read_bytes()

            # The file has to be compressed before packing
            if compression_status == 'C' and not is_compressed and auto_compress:
                file_data = pzz_compress(file_data)
            # The file has to be decompressed before packing
            elif compression_status == 'U' and is_compressed and auto_compress:
                file_data = pzz_decompress(file_data) # pad is not handled yet

            """
            # on ajoute le padding pour correspondre à un multiple de BLOCK_SIZE
            if compression_status == 'U':
                if (len(file_data) % BLOCK_SIZE) > 0:
                    file_data.extend(b"\x00" * (BLOCK_SIZE - (len(file_data) % BLOCK_SIZE)))
            """

            # file_descriptor = ceil of the len of the file / BLOCK_SIZE
            file_descriptor = ceil(len(file_data) / BLOCK_SIZE)

            # We add the compression flag bit to the file_descriptor
            if compression_status == 'C':
                file_descriptor |= BIT_COMPRESSION_FLAG

            header_bytes += file_descriptor.to_bytes(4, byteorder='big')
            pzz_file.write(file_data)

        pzz_file.seek(0)
        # We write the header
        pzz_file.write(header_bytes)


def unpzz(pzz_path:Path, folder_path:Path):
    pzz_unpack(pzz_path, folder_path, auto_decompress = True)


def pzz(folder_path:Path, pzz_file:Path):
    pzz_pack(folder_path, pzz_file, auto_compress = True)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='PZZ / MDT (de)compressor & unpacker - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-di', '--disable-ignore', action='store_true', help="Disable .pzzp or .pzz file extension verification.")
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-pzz', '--pzz',             action='store_true', help="-pzz source_folder (dest_file.pzz) : pzz source_folder in new file source_folder.pzz or dest_file if specified")
    group.add_argument('-unpzz', '--unpzz',         action='store_true', help="-unpzz source_folder.pzz (dest_folder) : unpzz the pzz in new folder source_folder or dest_folder if specified")
    group.add_argument('-bpzz', '--batch-pzz',      action='store_true', help='-bpzz source_folder (dest_folder) : Batch pzz (auto compress) all pzz_folder from source_folder into source_folder or dest_folder if specified')
    group.add_argument('-bunpzz', '--batch-unpzz',  action='store_true', help='-bunpzz source_folder (dest_folder) : Batch unpzz (auto decompress) all pzz from source_folder into source_folder or dest_folder if specified')
    group.add_argument('-p', '--pack',              action='store_true', help="-p source_folder (dest_file.pzz) : Pack source_folder in new file source_folder.pzz or dest_file if specified")
    group.add_argument('-u', '--unpack',            action='store_true', help='-u source_folder.pzz (dest_folder) : Unpack the pzz in new folder source_folder or dest_folder if specified')
    group.add_argument('-bp', '--batch-pack',       action='store_true', help='-bp source_folder (dest_folder) : Batch pack all pzz_folder from source_folder into source_folder or dest_folder if specified')
    group.add_argument('-bu', '--batch-unpack',     action='store_true', help='-bu source_folder (dest_folder) : Batch unpack all pzz from source_folder into source_folder or dest_folder if specified')
    group.add_argument('-c', '--compress',          action='store_true', help='-c source_file (dest_file) : compress source_file in source_file.pzzp or dest_file if specified')
    group.add_argument('-d', '--decompress',        action='store_true', help='-d source_file.pzzp (dest_file) : decompress source_file.pzzp in source_file or dest_file if specified')
    group.add_argument('-bc', '--batch-compress',   action='store_true', help='-bc source_folder dest_folder : compress all files from source_folder into dest_folder')
    group.add_argument('-bd', '--batch-decompress', action='store_true', help='-bd source_folder dest_folder : decompress all files from source_folder into dest_folder')
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.compress:
        logging.info("### Compress")
        if(p_output == Path(".")):
            p_output = Path(p_input.with_suffix(".pzzp"))

        # Extension check
        if not args.disable_ignore and p_input.suffix == ".pzzp":
            logging.warning(f"Ignored - {p_input} - bad extension - must not be a pzzp")
        elif not args.disable_ignore and p_output.suffix != ".pzzp":
            logging.warning(f"Ignored - {p_output} - bad extension - must be a pzzp")
        else:
            logging.info(f"Compressing {p_input} in {p_output}")
            p_output.write_bytes(pzz_compress(p_input.read_bytes()))
    elif args.decompress:
        logging.info("### Decompress")
        if p_output == Path("."):
            p_output = p_input.parent / p_input.stem

        # Extension check
        if not args.disable_ignore and p_input.suffix != ".pzzp":
            logging.warning(f"Ignored - {p_input} - bad extension - must be a pzzp")
        else:
            output_file_data = pzz_decompress(p_input.read_bytes())
            p_output = get_file_path(output_file_data, p_output)
            logging.info(f"Decompressing {p_input} in {p_output}")
            p_output.write_bytes(fix_pad_decompress(output_file_data, p_output))
    elif args.batch_compress:
        logging.info("### Batch Compress")
        if(p_output == Path(".")):
            p_output = Path(p_input)
        p_output.mkdir(exist_ok=True)

        for file_path in p_input.glob("*"):
            # Extension check
            if not args.disable_ignore and file_path.suffix == ".pzzp":
                logging.warning(f"Ignored - {file_path} - bad extension - musn't be a pzzp")
                if p_input != p_output:
                    shutil.copy(file_path, p_output/file_path.name)
                continue
            logging.info(f"Compressing {file_path}")
            (p_output/file_path.stem).with_suffix(".pzzp").write_bytes(pzz_compress(file_path.read_bytes()))
    elif args.batch_decompress:
        logging.info("### Batch Decompress")
        if(p_output == Path(".")):
            p_output = Path(p_input)
        p_output.mkdir(exist_ok=True)

        for file_path in p_input.glob("*"):
            if not args.disable_ignore and file_path.suffix != ".pzzp":
                logging.warning(f"Ignored - {file_path} - bad extension - must be a pzzp")
                if p_input != p_output:
                    shutil.copy(file_path, p_output / file_path.name)
                continue
            logging.info(f"Decompressing {file_path}")
            uncompressed_content = pzz_decompress(file_path.read_bytes())
            uncompressed_path = get_file_path(uncompressed_content, p_output / file_path.name)
            uncompressed_path.write_bytes(fix_pad_decompress(uncompressed_content, uncompressed_path))
    elif args.pack:
        logging.info("### Pack")
        pzz_pack(p_input, p_output)
    elif args.unpack:
        logging.info("### Unpack")
        pzz_unpack(p_input, p_output)
    elif args.pzz:
        logging.info("### PZZ")
        pzz(p_input, p_output)
    elif args.unpzz:
        logging.info("### UNPZZ")
        unpzz(p_input, p_output)
    elif args.batch_pack:
        logging.info("### Batch Pack")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for folder_path in p_input.glob("*"):
            pzz_pack(folder_path, p_output / Path(folder_path.name).with_suffix(".pzz"))
    elif args.batch_unpack:
        logging.info("### Batch Unpack")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for file_path in p_input.glob("*"):
            pzz_unpack(file_path, p_output / file_path.stem)
    elif args.batch_pzz:
        logging.info("### Batch PZZ")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for folder_path in p_input.glob("*"):
            pzz(folder_path, p_output / Path(folder_path.name).with_suffix(".pzz"))
    elif args.batch_unpzz:
        logging.info("### Batch UNPZZ")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for file_path in p_input.glob("*"):
            unpzz(file_path, p_output / file_path.stem)
