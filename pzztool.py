#!/usr/bin/env python3
from math import ceil
from struct import unpack, pack
from pathlib import Path
from os import listdir
__version__ = "1.2"
__author__ = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"
__license__ = "MIT"
__status__ = "developpement"


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

        print(compress_flag)
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
    success = False
    while not success:
        bout.extend(b"\x00\x00")
        address = len(bout)
        if hex(address).endswith("00"):
            break


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
    # Script BMS pour les pzz de ps2 (GioGio's adventure) -> https://zenhax.com/viewtopic.php?f=9&t=8724&p=39437#p39437
    if pzz_path.suffix != ".pzz":
        print("WARNING - Unpack : Invalid file format '" + pzz_path.suffix +
              "'; it should be .pzz file format")

    if dest_folder != Path('.'):
        unpacked_pzz_path = dest_folder
    else:
        unpacked_pzz_path = pzz_path.parent / pzz_path.stem
    unpacked_pzz_path.mkdir(exist_ok=True)

    with open(pzz_path, "rb") as pzz_file:
        # file_count reçoit le nombre de fichiers présent dans le PZZ :
        # On lit les 4 premiers octets (uint32 big-endian)
        file_count, = unpack(">I", pzz_file.read(4))

        # files_descriptors reçoit un tuple avec l'ensemble des descripteurs de fichiers (groupes d'uint32 big-endian)
        files_descriptors = unpack(">{}I".format(
            file_count), pzz_file.read(file_count * 4))

        print("File count:", file_count)

        offset = CHUNK_SIZE
        # on parcours le tuple de descripteurs de fichiers
        for index, file_descriptor in enumerate(files_descriptors):

            # Le bit 30 correspond au flag de compression (bits numérotés de 0 à 31)
            is_compressed = (file_descriptor & BIT_COMPRESSION_FLAG) != 0
            if not is_compressed:  # Si le fichier n'est pas compressé, on ajoute 'U' derrière l'index
                compression_status = 'U'
                comp_str = ""
            else:  # Si le fichier est compressé, on ajoute "_compressed" devant l'extension et 'C' derrière l'index
                compression_status = 'C'
                comp_str = "_compressed"

            # file_descriptor reçoit maintenant les 30 premiers bits : (la taille / CHUNK_SIZE)
            file_descriptor &= FILE_LENGTH_MASK

            # file_len reçoit la taille du fichier
            # la taille du fichier est un multiple de CHUNK_SIZE, on paddera avec des 0 jusqu'au fichier suivant
            # file_len contient alors la taille du fichier en octets
            file_len = file_descriptor * CHUNK_SIZE

            # On forme le nom du nouveau fichier que l'on va extraire
            filename = "{:03}{}_{}{}".format(
                index, compression_status, pzz_path.stem, comp_str)
            file_path = (unpacked_pzz_path / filename).with_suffix(".dat")

            print("Offset: {:010} - {}".format(offset, file_path.stem))

            # Si la taille est nulle, on créé un fichier vide et on passe au descripteur de fichier suivant
            if file_len == 0:
                file_path.touch()
                continue

            # On se positionne au début du fichier dans l'archive
            pzz_file.seek(offset)
            # On extrait notre fichier
            file_path.write_bytes(pzz_file.read(file_len))

            # Enfin, on ajoute la taille du fichier afin de pointer sur le fichier suivant
            # La taille du fichier étant un multiple de CHUNK_SIZE, on aura complété les 2048 octets finaux avec des 0x00
            offset += file_len


def pzz_pack(src_path, dest_file):
    # On récupère les fichiers du dossier à compresser
    src_files = listdir(src_path)

    # On récupère le nombre total de fichiers
    file_count = int(src_files[-1].split("_")[0][0:3]) + 1

    if dest_file != Path('.'):
        if dest_file.suffix != ".pzz":
            raise("Invalid file format : dest must be a pzz")
        pzz_path = dest_file
    else:
        pzz_path = src_path.with_suffix(".pzz")

    print(str(file_count) + " files to pack in " + str(pzz_path))

    with pzz_path.open("wb") as pzz_file:
        # On écrit file_count au début de header
        pzz_file.write(file_count.to_bytes(4, byteorder='big'))

        # On écrit les file_descriptor dans le header du PZZ pour chaque fichier
        for src_file_name in src_files:
            index = int(src_file_name.split("_")[0][0:3])

            # Compression status permet de verrifier si le fichier doit être finalement compressé ou non
            compression_status = src_file_name.split("_")[0][3:4]
            is_compressed = (len(src_file_name.split("_compressed")) > 1)

            # Le fichier doit être compressé avant d'être pack
            if compression_status == 'C' and is_compressed is False:
                pass
            # Le fichier doit être décompressé avant d'être pack
            elif compression_status == 'U' and is_compressed is True:
                pass

            # file_descriptor = arrondi supérieur de la taille / CHUNK_SIZE
            file_descriptor = ceil(
                (src_path / src_file_name).stat().st_size / CHUNK_SIZE)

            # On ajoute le flag de compression au file_descriptor
            if is_compressed:
                file_descriptor |= BIT_COMPRESSION_FLAG

            # On ecrit le file_descriptor
            pzz_file.write(file_descriptor.to_bytes(4, byteorder='big'))

        # On se place à la fin du header PZZ
        pzz_file.seek(CHUNK_SIZE)

        # On écrit tous les fichiers à la suite du header
        for src_file_name in src_files:
            is_compressed = (len(src_file_name.split("_compressed")) > 1)

            with (src_path / src_file_name).open("rb") as src_file:
                pzz_file.write(src_file.read())

                # Si le fichier n'est pas compressé, on ajoute le padding pour correspondre à un multiple de CHUNK_SIZE
                if not is_compressed and (src_file.tell() % CHUNK_SIZE) > 0:
                    pzz_file.write(
                        b"\x00" * (CHUNK_SIZE - (src_file.tell() % CHUNK_SIZE)))


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(
        description='PZZ (de)compressor & unpacker - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version',   action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('input_path',  metavar='INPUT',  help='')
    parser.add_argument('output_path', metavar='OUTPUT',
                        help='', nargs='?', default="")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',              action='store_true',
                       help="-p source_folder dest_file.pzz(optionnal) : Pack source_folder in new file source_folder.pzz")
    group.add_argument('-u', '--unpack',            action='store_true',
                       help='-u source_folder.pzz dest_folder(optionnal) : Unpack the pzz in new folder source_folder')
    group.add_argument('-bp', '--batch-pack',       action='store_true',
                       help='-bp source_folder dest_folder(optionnal - if not specified it will pack in source_folder)')
    group.add_argument('-bu', '--batch-unpack',     action='store_true',
                       help='INPUT relative pattern; e.g. AFS_DATA\\*.pzz')

    # group.add_argument('-a', '-aa',action='store_true', help='sha256')
    # group.add_argument('-c', '--compress',          action='store_true', help='')
    # group.add_argument('-d', '--decompress',        action='store_true', help='Unpacked files from PZZ')
    # group.add_argument('-bc', '--batch-compress',   action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*.bin')
    # group.add_argument('-bd', '--batch-decompress', action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*_compressed.dat')
    return parser


if __name__ == '__main__':
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)
    """
    if   args.compress:
        print("### Compress")
        p_output.write_bytes(pzz_compress(p_input.read_bytes()))
    elif args.decompress:
        print("### Decompress")
        p_output.write_bytes(pzz_decompress(p_input.read_bytes()))
    elif args.batch_compress:
        print("### Batch Compress")
        p_output.mkdir(exist_ok=True)

        p = Path('.')
        for filename in p.glob(args.input_path):
            print(filename)
            b = filename.read_bytes()
            (p_output / filename.name).with_suffix(".dat").write_bytes(pzz_compress(b))
    elif args.batch_decompress:
        print("### Batch Decompress")
        p_output.mkdir(exist_ok=True)

        p = Path('.')
        for filename in p.glob(args.input_path):
            print(filename)
            try:
                b = filename.read_bytes()
                (p_output / filename.name).with_suffix(".bin").write_bytes(pzz_decompress(b))
            except IndexError:
                print("! Wrong PZZ file")
    el
    """
    if args.pack:
        print("### Pack")
        pzz_pack(p_input, p_output)
    elif args.unpack:
        print("### Unpack")
        pzz_unpack(p_input, p_output)
    elif args.batch_pack:
        print("### Batch Pack")
        p_output.mkdir(exist_ok=True)

        for folder in listdir(p_input):
            pzz_pack(p_input / folder, p_output /
                     Path(folder).with_suffix(".pzz"))
    elif args.batch_unpack:
        print("### Batch Unpack")
        p_output.mkdir(exist_ok=True)

        for filename in listdir(p_input):
            pzz_unpack(p_input / filename, p_output / Path(filename).stem)

    """
        Code pour le developement --> pzztool.py -a a
        compare le sha256 de chaque PZZ du dossier pzz et pzz2 puis affiche le nom de fichier en cas de différence
    import hashlib
    for pzz_file in listdir("pzz"):
        with open("pzz/"+pzz_file, "rb") as f1, open("pzz2/"+pzz_file, "rb") as f2:
            if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
                print(pzz_file)
    """
