#!/usr/bin/env python3
from math import ceil
from pathlib import Path
from struct import unpack
from os import listdir
import logging

__version__ = "1.3.11"
__author__ = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"
__license__ = "MIT"
__status__ = "developpement"


# Pour plus d'informations sur le format PZZ :
# http://virtualre.rf.gd/index.php/PZZ_(Gotcha_Force)


BIT_COMPRESSION_FLAG = 0x40000000
FILE_LENGTH_MASK = 0x3FFFFFFF
CHUNK_SIZE = 0x800


def pzz_decompress(compressed_bytes: bytes):
    uncompressed_bytes = bytearray()
    compressed_bytes_size = len(compressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = -1
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

        # logging.debug(compress_flag)
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
                uncompressed_bytes.append(uncompressed_bytes[index + j])
        else:
            uncompressed_bytes.extend(compressed_bytes[i: i + 2])
        i += 2

    return uncompressed_bytes


def bytes_align(bout: bytes):
    while len(bout) % CHUNK_SIZE > 0:
        bout.extend(b"\x00")


def pzz_compress(b):
    bout = bytearray()
    size_b = len(b) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = 15
    cb_pos = 0
    bout.extend(b"\x00\x00")

    i = 0
    while i < size_b:
        start = max(i - 0x7FF * 2, 0)
        count_r = 0
        max_i = -1
        tmp = b[i: i + 2]
        init_count = len(tmp)
        while True:
            start = b.find(tmp, start, i + 1)
            if start != -1 and start % 2 != 0:
                start += 1
                continue
            if start != -1:
                count = init_count
                while i < size_b - count \
                        and count < 0xFFFF * 2 \
                        and b[start + count] == b[i + count] \
                        and b[start + count + 1] == b[i + count + 1]:
                    count += 2
                if count_r < count:
                    count_r = count
                    max_i = start
                start += 2
            else:
                break
        start = max_i

        compress_flag = 0
        if count_r >= 4:
            compress_flag = 1
            offset = i - start
            offset //= 2
            count_r //= 2
            c = offset
            if count_r <= 0x1F:
                c |= count_r << 11
                bout.append((c >> 8))
                bout.append(c & 0xFF)
            else:
                bout.append((c >> 8))
                bout.append(c & 0xFF)
                bout.append((count_r >> 8))
                bout.append(count_r & 0xFF)
            i += count_r * 2
        else:
            bout.extend(b[i: i + 2])
            i += 2
        cb |= (compress_flag << cb_bit)
        cb_bit -= 1
        if cb_bit < 0:
            bout[cb_pos + 1] = cb & 0xFF
            bout[cb_pos + 0] = cb >> 8
            cb = 0x0000
            cb_bit = 15
            cb_pos = len(bout)
            bout.extend(b"\x00\x00")

    cb |= (1 << cb_bit)
    bout[cb_pos + 1] = cb & 0xFF
    bout[cb_pos + 0] = cb >> 8
    bout.extend(b"\x00\x00")

    bytes_align(bout)

    return bout


def pzz_unpack(pzz_path, dest_folder):
    if pzz_path.suffix != ".pzz":
        logging.warning(f"Invalid file format '{pzz_path.suffix}'; it should be .pzz file format")

    if dest_folder != Path('.'):
        unpacked_pzz_path = dest_folder
    else:
        unpacked_pzz_path = pzz_path.parent / pzz_path.stem

    logging.info(f"    unpacking {pzz_path} in folder {unpacked_pzz_path}")
    unpacked_pzz_path.mkdir(exist_ok=True)

    with open(pzz_path, "rb") as pzz_file:
        # file_count reçoit le nombre de fichiers présent dans le PZZ :
        # On lit les 4 premiers octets (uint32 big-endian)
        file_count, = unpack(">I", pzz_file.read(4))

        # files_descriptors reçoit un tuple avec l'ensemble des descripteurs de fichiers (groupes d'uint32 big-endian)
        files_descriptors = unpack(f">{file_count}I", pzz_file.read(file_count * 4))

        logging.debug(f"    -> File count : {file_count}")

        offset = CHUNK_SIZE
        # on parcours le tuple de descripteurs de fichiers
        for index, file_descriptor in enumerate(files_descriptors):

            # Le bit 30 correspond au flag de compression (bits numérotés de 0 à 31)
            is_compressed = (file_descriptor & BIT_COMPRESSION_FLAG) != 0
            if not is_compressed:  # Si le fichier n'est pas compressé, on ajoute 'U' derrière l'index
                compression_status = 'U'
            else:  # Si le fichier est compressé, on ajoute "_compressed" devant l'extension et 'C' derrière l'index
                compression_status = 'C'

            # file_descriptor reçoit maintenant les 30 premiers bits : (la taille / CHUNK_SIZE)
            file_descriptor &= FILE_LENGTH_MASK

            # file_len reçoit la taille du fichier
            # la taille du fichier est un multiple de CHUNK_SIZE, on paddera avec des 0 jusqu'au fichier suivant
            # file_len contient alors la taille du fichier en octets
            file_len = file_descriptor * CHUNK_SIZE

            # On forme le nom du nouveau fichier que l'on va extraire
            filename = f"{index:03}{compression_status}_{pzz_path.stem}"
            file_path = (unpacked_pzz_path / filename).with_suffix(".dat")

            logging.debug(f"    -> Offset: {offset:010} - {file_path.stem}")

            # Si la taille est nulle, on créé un fichier vide et on passe au descripteur de fichier suivant
            if file_len == 0:
                file_path.touch()
                continue

            # On se positionne au début du fichier dans l'archive
            pzz_file.seek(offset)
            # On extrait notre fichier et on le décompresse
            if compression_status == 'C':
                file_path.write_bytes(pzz_decompress(pzz_file.read(file_len)))
            else:
                file_path.write_bytes(pzz_file.read(file_len))

            # Enfin, on ajoute la taille du fichier afin de pointer sur le fichier suivant
            # La taille du fichier étant un multiple de CHUNK_SIZE, on aura complété les 2048 octets finaux avec des 0x00
            offset += file_len


def pzz_pack(src_path, dest_file):
    # On récupère les fichiers du dossier à compresser
    src_files = listdir(src_path)

    # On récupère le nombre total de fichiers
    file_count = len(src_files)

    if dest_file != Path('.'):
        if dest_file.suffix != ".pzz":
            raise("Invalid file format : dest must be a pzz")
        pzz_path = dest_file
    else:
        pzz_path = src_path.with_suffix(".pzz")
    logging.info(f"    packing {src_path} in pzz {pzz_path}")
    logging.debug(f"    -> {file_count} files to pack")

    with pzz_path.open("wb") as pzz_file:
        # On écrit file_count au début de header
        pzz_file.write(file_count.to_bytes(4, byteorder='big'))

        # On se place à la fin du header PZZ
        pzz_file.seek(CHUNK_SIZE)

        file_descriptors = []
        # On écrit tous les fichiers à la suite du header
        for src_file_name in src_files:
            is_compressed = "_compressed" in src_file_name
            compression_status = src_file_name[3:4]

            with (src_path / src_file_name).open("rb") as src_file:
                src_file = src_file.read()

                # Le fichier doit être compressé avant d'être pack
                if compression_status == 'C' and not is_compressed:
                    src_file = pzz_compress(src_file)
                # Le fichier doit être décompressé avant d'être pack
                elif compression_status == 'U' and is_compressed:
                    src_file = pzz_decompress(src_file) # padding à gérer

                # on ajoute le padding pour correspondre à un multiple de CHUNK_SIZE
                if compression_status == 'U':
                    if (len(src_file) % CHUNK_SIZE) > 0:
                        src_file.extend(b"\x00" * (CHUNK_SIZE - (len(src_file) % CHUNK_SIZE)))
                

                # file_descriptor = arrondi supérieur de la taille / CHUNK_SIZE
                file_descriptor = ceil(len(src_file) / CHUNK_SIZE)

                # On ajoute le flag de compression au file_descriptor
                if compression_status == 'C':
                    file_descriptor |= BIT_COMPRESSION_FLAG

                file_descriptors.append(file_descriptor)
                pzz_file.write(src_file)

        pzz_file.seek(4)
        # On écrit les file_descriptor dans le header du PZZ pour chaque fichier
        tmp = bytearray()
        for file_descriptor in file_descriptors:
            tmp.extend(file_descriptor.to_bytes(4, byteorder='big'))
        pzz_file.write(tmp)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='PZZ (de)compressor & unpacker - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version',   action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT',  help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',              action='store_true', help="-p source_folder dest_file.pzz(optionnal) : Pack source_folder in new file source_folder.pzz")
    group.add_argument('-u', '--unpack',            action='store_true', help='-u source_folder.pzz dest_folder(optionnal) : Unpack the pzz in new folder source_folder')
    group.add_argument('-bp', '--batch-pack',       action='store_true', help='-bp source_folder dest_folder(optionnal - if not specified it will pack in source_folder)')
    group.add_argument('-bu', '--batch-unpack',     action='store_true', help='-bu source_folder dest_folder(optionnal - if not specified it will unpack in source_folder)')
    group.add_argument('-c', '--compress',          action='store_true', help='')
    group.add_argument('-d', '--decompress',        action='store_true', help='Unpacked files from PZZ')
    group.add_argument('-bc', '--batch-compress',   action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*.bin')
    group.add_argument('-bd', '--batch-decompress', action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*_compressed.dat')
    group.add_argument('-di', '--disable-ignore',   action='store_true', help="Disable filename ignore")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.compress:
        logging.info("### Compress")
        p_output.write_bytes(pzz_compress(p_input.read_bytes()))
    elif args.decompress:
        logging.info("### Decompress")
        p_output.write_bytes(pzz_decompress(p_input.read_bytes()))
    elif args.batch_compress:
        logging.info("### Batch Compress")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            if (not args.disable_ignore) and not ("_compressed" in filename):
                logging.debug(f"Compressing {filename}")
                recomp_filename = f"{Path(filename).stem}_compressed{Path(filename).suffix}"

                with open(p_input / filename, 'rb') as uncompressed, open(p_output / filename, 'wb') as recompressed:
                    recompressed.write(pzz_compress(uncompressed.read()))
            else:
                logging.info(f"Ignored: {filename}")
    elif args.batch_decompress:
        logging.info("### Batch Decompress")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            if (not args.disable_ignore) and ("_compressed" in filename):
                logging.info(f"Decompressing {filename}")
                uncomp_filename = filename.replace("_compressed", "")

                with open(p_output / uncomp_filename, 'wb') as uncompressed, open(p_input / filename, 'rb') as compressed:
                    uncompressed.write(pzz_decompress(compressed.read()))
            else:
                logging.info(f"Ignored: {filename}")
    elif args.pack:
        logging.info("### Pack")
        pzz_pack(p_input, p_output)
    elif args.unpack:
        logging.info("### Unpack")
        pzz_unpack(p_input, p_output)
    elif args.batch_pack:
        logging.info("### Batch Pack")
        p_output.mkdir(exist_ok=True)

        for folder in listdir(p_input):
            pzz_pack(p_input / folder, p_output / Path(folder).with_suffix(".pzz"))
    elif args.batch_unpack:
        logging.info("### Batch Unpack")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            pzz_unpack(p_input / filename, p_output / Path(filename).stem)
