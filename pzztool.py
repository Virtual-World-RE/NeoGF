#!/usr/bin/env python3
__version__ = "1.0"
__author__  = "rigodron, algoflash, GGLinnk"
__OriginalAutor__ = "infval"

from os import listdir, path, stat
from pathlib import Path
from struct import unpack, pack


def pzz_decompress(compressed_bytes: bytes):
    uncompressed_bytes = bytearray()
    compressed_bytes_size = len(compressed_bytes) // 2 * 2

    cb = 0  # Control bytes
    cb_bit = -1
    i = 0
    while i < compressed_bytes_size:
        if cb_bit < 0:
            cb  = compressed_bytes[i + 1]
            cb |= compressed_bytes[i + 0] << 8
            cb_bit = 15
            i += 2
            continue

        compress_flag = cb & (1 << cb_bit)
        cb_bit -= 1

        print(compress_flag)
        if compress_flag:
            c  = compressed_bytes[i + 1]
            c |= compressed_bytes[i + 0] << 8
            offset = (c & 0x7FF) * 2
            if offset == 0:
                break # End of the compressed data
            count = (c >> 11) * 2
            if count == 0:
                i += 2
                c  = compressed_bytes[i + 1]
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


def pzz_unpack(path, dir_path):
    """ BMS script: https://zenhax.com/viewtopic.php?f=9&t=8724&p=39437#p39437
    """
    with open(path, "rb") as f:
        file_count = f.read(4) # file_count contient le nombre de fichiers dans le PZZ
        file_count, = unpack(">I", file_count) # big-endian uint32

        size = f.read(file_count * 4)
        # size contient l'ensemble des descripteurs de fichiers du header PZZ
        size = unpack(">{}I".format(file_count), size)
        # size contient les descripteurs de fichiers au format uint32

        print("File count:", file_count)

        offset = 0x800
        # Le PZZ contient le header et les fichiers séparés tous les 0x800
        for i, s in enumerate(size): # on a un ensemble d'uint32 et leur index qu'on parcours
            is_compressed = (s & 0x40000000) != 0 # "& bit à bit" avec le bit de compression (bit30)
            
            s &= 0x3FFFFFFF # s contient maintenant la taille du fichier sans les bits de flag (bit30, bit31)
            s *= 0x800 # taille fichier * 0x800

            if s == 0:
                continue
            comp_str = ""
            if is_compressed:
                comp_str = "_compressed"
            filename = "{}_{:03}{}".format(Path(path).stem, i, comp_str)
            p = (Path(dir_path) / filename).with_suffix(".dat")

            print("Offset: {:010} - {}".format(offset, p))

            f.seek(offset)
            p.write_bytes(f.read(s))
            offset += s

def pzz_pack(src, dir_path):
    bout = bytearray()
    filebout = bytearray()
    file_count = 0;
    files = []

    linkPath = path.normpath(dir_path)
    linkFiles = [f for f in listdir(linkPath) if path.isfile(path.join(linkPath, f))]

    for file in linkFiles:
        if (str(src)[12:-18] in file):
            file_count += 1
            files.append(file)

    is_odd_number = (file_count % 2) != 0

    if (file_count == 6 or file_count == 12):
        file_count += 4
        for i, file in enumerate(files):
            count = int(0x40 << 24) + int(path.getsize(linkPath + "/" + file) / 0x800)

            if (i == 1 or i == 3 or i == 5 or i == 7):
                filebout.extend(b"\x00\x00\x00\x00")
                filebout.extend(pack(">I", count))
            else:
                filebout.extend(pack(">I", count))

        file_count = pack(">I", file_count)
        bout.extend(file_count)
        bout.extend(filebout)

    elif (file_count == 6 or file_count == 14):
        file_count += 2
        for i, file in enumerate(files):
            count = int(0x40 << 24) + int(path.getsize(linkPath + "/" + file) / 0x800)

            if (i == 1 or i == 3):
                filebout.extend(b"\x00\x00\x00\x00")
                filebout.extend(pack(">I", count))
            else:
                filebout.extend(pack(">I", count))

        file_count = pack(">I", file_count)
        bout.extend(file_count)
        bout.extend(filebout)

    elif is_odd_number:
        file_count += 1
        for i, file in enumerate(files):
            count = int(0x40 << 24) + int(path.getsize(linkPath + "/" + file) / 0x800)

            if (i == 1):
                filebout.extend(b"\x00\x00\x00\x00")
                filebout.extend(pack(">I", count))
            else:
                filebout.extend(pack(">I", count))

        file_count = pack(">I", file_count)
        bout.extend(file_count)
        bout.extend(filebout)

    success = False

    while not success:
        bout.extend(b"\x00\x00")
        address = len(bout)
        if hex(address).endswith("800"):
            break
    for file in files:
        filebout = open(linkPath + "/" + file, "rb")
        data = filebout.read()
        bout.extend(data)
    filename = "{}".format(str(src)[12:-19])
    p = (Path(dir_path) / filename).with_suffix(".pzz")
    p.write_bytes(bout)

def pzz_test():
    print(pack(">I", int(0x40 << 24) + int(stat(linkPath + "/" + file).st_size) / 0x800))

def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='PZZ (de)compressor & unpacker - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('input_path', metavar='INPUT', help='only relative if -bu, -bc, -bd, p')
    parser.add_argument('output_path', metavar='OUTPUT', help='directory if -u, -bu, -bc, -bd')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--unpack', action='store_true', help='PZZ files from AFS')
    group.add_argument('-c', '--compress', action='store_true')
    group.add_argument('-d', '--decompress', action='store_true', help='Unpacked files from PZZ')
    group.add_argument('-bu', '--batch-unpack', action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*.pzz')
    group.add_argument('-bc', '--batch-compress', action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*.bin')
    group.add_argument('-bd', '--batch-decompress', action='store_true', help='INPUT relative pattern; e.g. AFS_DATA\\*_compressed.dat')
    group.add_argument('-p', '--pack', action='store_true')
    group.add_argument('-t', '--test', action='store_true')
    return parser


if __name__ == '__main__':
    import sys
    parser = get_argparser()
    args = parser.parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)
    if args.compress:
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
    elif args.pack:
        print("### Pack")
        p_output.mkdir(exist_ok=True)
        pzz_pack(p_input, p_output)
    elif args.test:
        pzz_test()
    elif args.unpack:
        print("### Unpack")
        p_output.mkdir(exist_ok=True)
        pzz_unpack(p_input, p_output)
    #elif args.batch_pack:
    #    pass
    elif args.batch_unpack:
        print("### Batch Unpack")
        p_output.mkdir(exist_ok=True)

        p = Path('.')
        for filename in p.glob(args.input_path):
            print(filename)
            pzz_unpack(filename, p_output)

            
