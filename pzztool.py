#!/usr/bin/env python3
from math import ceil
from pathlib import Path
import shutil
from struct import unpack
from os import listdir
import logging

__version__ = "1.4.2"
__author__ = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"
__license__ = "MIT"
__status__ = "developpement"


# Pour plus d'informations sur le format PZZ :
# http://virtualre.rf.gd/index.php/PZZ_(Gotcha_Force)


BIT_COMPRESSION_FLAG = 0x40000000
FILE_LENGTH_MASK = 0x3FFFFFFF
CHUNK_SIZE = 0x800
TPL_MAGIC_NUMBER = b"\x00\x20\xAF\x30" # http://virtualre.rf.gd/index.php/TPL_(Format_de_fichier)
CHD_MAGIC_NUMBER = b"Head"
BIN_HITS_MAGICNUMBER = b"STIH"
TSB_MAGIC_NUMBER = b"TSBD"

def get_file_path(file_content: bytes, path: Path):
    if path.name[5:7] == "pl": # si c'est un plxxxx
        if path.name[0:3] == "000":
            return path.with_name(path.name + "data").with_suffix(".bin")
        if path.name[0:3] == "002":
            return path.with_name(path.name + "hit").with_suffix(".bin")
        if path.name[0:3] == "003":
            return path.with_name(path.name + "mot").with_suffix(".bin")
    if file_content.startswith(TPL_MAGIC_NUMBER):
        return path.with_suffix(".tpl")
    if file_content.startswith(CHD_MAGIC_NUMBER):
        return path.with_suffix(".chd")
    if file_content.startswith(TSB_MAGIC_NUMBER):
        return path.with_suffix(".tsb")
    if file_content.startswith(BIN_HITS_MAGICNUMBER):
        return path.with_suffix(".bin")
    # Par défaut
    return path.with_suffix(".dat")

# Non implémenté : pour supprimer le pad à la fin des fichiers unpack
# Les fichiers sans pad se terminent éventuellement par des b"\x00"
#     ce qui impose de connaître le format de fichier pour implémenter cette fonction
def remove_padding(file_content: bytearray):
    return file_content
    # return file_content.rstrip(b'\x00')


def bytes_align(bout: bytes):
    # Comme le montre le fichier pl080d/006C_pl080d.pzzp, on ajoute 0x800 si c'est aligné sur un multiple
    if len(bout) % CHUNK_SIZE == 0:
        return bout.ljust(CHUNK_SIZE * (len(bout) / CHUNK_SIZE + 1), b"\x00")
    return bout.ljust(CHUNK_SIZE * ceil(len(bout) / CHUNK_SIZE), b"\x00")


def pzz_decompress(compressed_bytes: bytes):
    uncompressed_bytes = bytearray()
    compressed_bytes_size = len(compressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = -1 # rotations de 15 à 0 pour le flag de compression
    i = 0
    while i < compressed_bytes_size:
        if cb_bit < 0: # tous les 
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
                uncompressed_bytes.append(uncompressed_bytes[index + j])
        else:
            uncompressed_bytes += compressed_bytes[i: i+2]
        i += 2

    return uncompressed_bytes


def pzz_compress(uncompressed_bytes: bytes):
    compressed_bytes = bytearray(2)
    size_uncompressed_bytes = len(uncompressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = 15 # rotations de 15 à 0 pour le flag de compression
    cb_pos = 0

    i = 0
    while i < size_uncompressed_bytes:
        start = max(i - 4094, 0) # start = 2 si i = 4096 (0x800*2)
        count_r = 0
        max_i = -1

        #######################################################
        # start : contient l'index .. (en cours de rédaction)
        #######################################################
        while True:
            # start = index première occurence de uncompressed_bytes[i:i+2] entre start et i+1
            #     on regarde maxi dans les 4094 derniers octets
            start = uncompressed_bytes.find(uncompressed_bytes[i: i+2], start, i+1)

            # si les 2 octets étudiés n'apparaissent pas dans les 4094 derniers octets
            if start == -1:
                break

            # si la première occurence n'est pas à un index multiple de 2, on l'ignore
            if start % 2 != 0:
                start += 1
                continue
            count = 2
            while   i < size_uncompressed_bytes - count and \
                    count < 0xFFFF * 2  and \
                    uncompressed_bytes[start+count]   == uncompressed_bytes[i+count] and \
                    uncompressed_bytes[start+count+1] == uncompressed_bytes[i+count+1]:
                count += 2
            if count_r < count:
                count_r = count
                max_i = start
            start += 2
        start = max_i

        #######################################################
        # 
        #######################################################
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

    return bytes_align(compressed_bytes)


def pzz_unpack(pzz_path: Path, dest_folder: Path, auto_decompress: bool = False):
    if pzz_path.suffix != ".pzz":
        logging.warning(f"Invalid file format '{pzz_path.suffix}'; it should be .pzz file format")

    if dest_folder != Path('.'):
        unpacked_pzz_path = dest_folder
    else:
        unpacked_pzz_path = pzz_path.parent / pzz_path.stem

    if(auto_decompress):
        logging.info(f"    unpzz({pzz_path}) in folder {unpacked_pzz_path}")
    else:
        logging.info(f"    unpacking {pzz_path} in folder {unpacked_pzz_path}")
    unpacked_pzz_path.mkdir(exist_ok=True)

    with pzz_path.open("rb") as pzz_file:
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
            else:  # Si le fichier est compressé on ajoute 'C' derrière l'index et l'extension ".pzzp"
                compression_status = 'C'

            # file_descriptor reçoit maintenant les 30 premiers bits : (la taille / CHUNK_SIZE)
            file_descriptor &= FILE_LENGTH_MASK

            # file_len reçoit la taille du fichier
            # la taille du fichier est un multiple de CHUNK_SIZE, on paddera avec des 0 jusqu'au fichier suivant
            # file_len contient alors la taille du fichier en octets
            file_len = file_descriptor * CHUNK_SIZE

            # On forme le nom du nouveau fichier que l'on va extraire
            filename = f"{index:03}{compression_status}_{pzz_path.stem}"
            file_path = unpacked_pzz_path / filename

            logging.debug(f"    -> Offset: {offset:010} - {file_path}")

            # Si la taille est nulle, on créé un fichier vide et on passe au descripteur de fichier suivant
            if file_len == 0:
                file_path.with_suffix(".dat").touch()
                continue

            # On se positionne au début du fichier dans l'archive
            pzz_file.seek(offset)
            # On extrait notre fichier et on le décompresse
            if compression_status == 'C' and auto_decompress:
                file_content = pzz_decompress(pzz_file.read(file_len))
            else:
                file_content = pzz_file.read(file_len)

            file_content = remove_padding(bytearray(file_content))

            if not auto_decompress and compression_status != 'U':
                file_path = file_path.with_suffix(".pzzp")
            else:
                file_path = get_file_path(file_content, file_path)

            file_path.write_bytes(file_content)

            # Enfin, on ajoute la taille du fichier afin de pointer sur le fichier suivant
            # La taille du fichier étant un multiple de CHUNK_SIZE, on aura complété les 2048 octets finaux avec des 0x00
            offset += file_len


def pzz_pack(src_path: Path, dest_file: Path, auto_compress: bool = False):
    if dest_file == Path('.'):
        dest_file = src_path.with_suffix(".pzz")
    if dest_file.suffix != ".pzz":
        logging.warning("Invalid file format : dest must be a pzz")

    # On récupère les fichiers du dossier à compresser
    src_files = listdir(src_path)

    if auto_compress:
        logging.info(f"    pzz({src_path}) in pzz {dest_file}")
    else:
        logging.info(f"    packing {src_path} in pzz {dest_file}")
    logging.debug(f"    -> {len(src_files)} files to pack")

    with dest_file.open("wb") as pzz_file:
        # On se place à la fin du header PZZ
        pzz_file.seek(CHUNK_SIZE)

        # On récupère le nombre total de fichiers pour le mettre au début du header
        header_bytes = len(src_files).to_bytes(4, byteorder='big')

        # On écrit tous les fichiers à la suite du header
        for src_file_name in src_files:
            is_compressed = Path(src_file_name).suffix == ".pzzp"
            compression_status = src_file_name[3:4]

            src_file = (src_path / src_file_name).read_bytes()

            # Le fichier doit être compressé avant d'être pack
            if compression_status == 'C' and not is_compressed and auto_compress:
                src_file = pzz_compress(src_file)
            # Le fichier doit être décompressé avant d'être pack
            elif compression_status == 'U' and is_compressed and auto_compress:
                src_file = pzz_decompress(src_file) # padding à gérer

            """
            # on ajoute le padding pour correspondre à un multiple de CHUNK_SIZE
            if compression_status == 'U':
                if (len(src_file) % CHUNK_SIZE) > 0:
                    src_file.extend(b"\x00" * (CHUNK_SIZE - (len(src_file) % CHUNK_SIZE)))
            """

            # file_descriptor = arrondi supérieur de la taille / CHUNK_SIZE
            file_descriptor = ceil(len(src_file) / CHUNK_SIZE)

            # On ajoute le flag de compression au file_descriptor
            if compression_status == 'C':
                file_descriptor |= BIT_COMPRESSION_FLAG

            header_bytes += file_descriptor.to_bytes(4, byteorder='big')
            pzz_file.write(src_file)

        pzz_file.seek(0)
        # On écrit le header
        pzz_file.write(header_bytes)


def unpzz(src_path: Path, dest_file: Path):
    pzz_unpack(src_path, dest_file, auto_decompress = True)


def pzz(src_path: Path, dest_file: Path):
    pzz_pack(src_path, dest_file, auto_compress = True)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='PZZ (de)compressor & unpacker - [GameCube] Gotcha Force v' + __version__)
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

        # Si on a pas la bonne extension on ne compresse pas le fichier
        if not args.disable_ignore and p_output.suffix != ".pzzp":
            logging.warning(f"Ignored - {p_output} - bad extension - must be a pzzp")
        else:
            logging.info(f"Compressing {p_input} in {p_output}")
            p_output.write_bytes(pzz_compress(p_input.read_bytes()))
    elif args.decompress:
        logging.info("### Decompress")
        if p_output == Path("."):
            p_output = p_input.parent / p_input.stem

        # Si on a pas la bonne extension on ne decompresse pas le fichier
        if not args.disable_ignore and p_input.suffix != ".pzzp":
            logging.warning(f"Ignored - {p_input} - bad extension - must be a pzzp")
        else:
            output_file_content = pzz_decompress(p_input.read_bytes())
            p_output = get_file_path(output_file_content, p_output)
            logging.info(f"Decompressing {p_input} in {p_output}")
            p_output.write_bytes(output_file_content)
    elif args.batch_compress:
        logging.info("### Batch Compress")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            # Si on a pas la bonne extension on ne compresse pas le fichier
            if not args.disable_ignore and Path(filename).suffix == ".pzzp":
                logging.warning(f"Ignored - {filename} - bad extension - musn't be a pzzp")
                shutil.copy(p_input / filename, p_output / filename)
                continue
            logging.info(f"Compressing {filename}")
            (p_output / (Path(filename).stem + ".pzzp")).write_bytes(pzz_compress((p_input / filename).read_bytes()))
    elif args.batch_decompress:
        logging.info("### Batch Decompress")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            if not args.disable_ignore and Path(filename).suffix != ".pzzp":
                logging.warning(f"Ignored - {filename} - bad extension - must be a pzzp")
                shutil.copy(p_input / filename, p_output / filename)
                continue
            logging.info(f"Decompressing {filename}")
            uncompressed_content = pzz_decompress((p_input / filename).read_bytes())
            uncompressed_path = get_file_path(uncompressed_content, p_output / Path(filename))
            uncompressed_path.write_bytes(uncompressed_content)
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
        for folder in listdir(p_input):
            pzz_pack(p_input / folder, p_output / Path(folder).with_suffix(".pzz"))
    elif args.batch_unpack:
        logging.info("### Batch Unpack")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for filename in listdir(p_input):
            pzz_unpack(p_input / filename, p_output / Path(filename).stem)
    elif args.batch_pzz:
        logging.info("### Batch PZZ")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for folder in listdir(p_input):
            pzz(p_input / folder, p_output / Path(folder).with_suffix(".pzz"))
    elif args.batch_unpzz:
        logging.info("### Batch UNPZZ")
        p_output.mkdir(exist_ok=True)

        if(p_output == Path('.')):
            p_output = p_input
        for filename in listdir(p_input):
            unpzz(p_input / filename, p_output / Path(filename).stem)
