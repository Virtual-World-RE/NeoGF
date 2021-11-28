import argparse
import hashlib
import os
from pathlib import Path
import pzztool
import shutil


TPL_MAGIC_NUMBER = b"\x00\x20\xAF\x30" # http://virtualre.rf.gd/index.php/TPL_(Format_de_fichier)


# compare le sha256 de chaque PZZ des dossiers passés en argument
#     -> affiche le nom de fichier en cas de différence
def verify_sha256(folder1: Path, folder2: Path):
    invalid_files_count = 0
    for pzz_file_name in os.listdir(folder1):
        with (folder1 / pzz_file_name).open("rb") as f1, (folder2 / pzz_file_name).open("rb") as f2:
            if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
                print(f"ERROR - INVALID FILE : {pzz_file_name}")
                invalid_files_count +=1
    print(f"Invalid files : {invalid_files_count}/{len(os.listdir(folder1))}")

# compare le sha256 des deux fichiers passés en argument
#     -> affiche le nom de fichier en cas de différence
def verify_sha256_2(file1: Path, file2: Path):
    with file1.open("rb") as f1, file2.open("rb") as f2:
        if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
            return False
    return True


def get_argparser():
    parser = argparse.ArgumentParser(description='TEST TOOL')
    parser.add_argument('input_path',  metavar='INPUT',  help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-tdc',  '--test-decompress-compress',   action='store_true', help="")
    group.add_argument('-tbup', '--test-batch-unpack-pack',     action='store_true', help="""
        -tbup source_pzz_folder
            source_pzz_folder  : put all pzz in this folder
            pzzu : will be created with all unpacked pzz from pzz folder
            pzz2 : will be created with all packed pzz from pzzu folder
        print file_name when sha256 is different between source_pzz_folder and pzz2 folder""")
    group.add_argument('-tbunpzzpzz', '--test-batch-unpzz-pzz', action='store_true', help="""
        -tbunpzzpzz source_pzz_folder
            source_pzz_folder  : put all pzz in this folder
            pzzu : will be created with all unpzz pzz from pzz folder
            pzz2 : will be created with all pzz(pzz_folder) from pzzu folder
        print file_name when sha256 is different between source_pzz_folder and pzz2 folder""")
    group.add_argument('-tctplh', '--test-check-tpl-headers',   action='store_true', help="-tctplh afs_data_folder : check all files headers in the afs_data and print those who have the tpl magicfile")
    group.add_argument('-tcd', '--test-check-decompress',       action='store_true', help="""
        pzz : put all pzz in this folder
        then tip "pzztool.py -tcd pzz"
        The script will then check that tpls are correctly decompressed with their specific characteristics""")
    group.add_argument('-tcp', '--test-compare-position',   action='store_true', help="compare plxxxx.pzz subfiles with plxxxx files inside afs_data.afs")
    return parser


if __name__ == '__main__':
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)

    if args.test_decompress_compress:
        print("# TEST : DECOMPRESS COMPRESS")
        listofinvalid = []

        for filename in os.listdir(args.input_path):
            file = open(os.path.join(args.input_path, filename), 'rb')
            original_bytes = file.read()
            decomp_bytes = pzztool.pzz_decompress(original_bytes)
            recomp_bytes = pzztool.pzz_compress(decomp_bytes)

            original_digest = hashlib.sha256(original_bytes).hexdigest()
            recomp_digest = hashlib.sha256(recomp_bytes).hexdigest()

            if original_digest != recomp_digest:
                listofinvalid.append(f"{filename} : ({original_digest}) ({recomp_digest})")
            file.close()

        for invalid in listofinvalid:
            print(invalid)
    elif args.test_batch_unpack_pack:
        print("# TEST : BATCH UNPACK PACK")

        os.system(f"python pzztool.py -bu {args.input_path} pzzu")
        os.system("python pzztool.py -bp pzzu pzz2")
        verify_sha256(p_input, Path("pzz2"))
    elif args.test_batch_unpzz_pzz:
        os.system(f"python pzztool.py -bunpzz {args.input_path} pzzu")
        os.system("python pzztool.py -bpzz pzzu pzz2")
        verify_sha256(p_input, Path("pzz2"))

        # Clean du dossier pzz2 généré par le script
        shutil.rmtree("pzz2")

        """
            si pzz : U -> decomp / testé sur les fichiers car l'unpzz décompresse par défaut
            si pzz : U -> comp   / à tester
            si pzz : C -> decomp / testé sur les fichiers car l'unpzz décompresse par défaut
            si pzz : C -> comp   / à tester
        """
        # On parcours tous les dossiers : si U -> comp ; si C -> comp : compression de tous les fichiers peu importe le type
        for pzz_folder in os.listdir("pzzu"):
            for pzz_file_part_name in os.listdir("pzzu/"+pzz_folder):
                # créé un nouveau fichier compressé, à côté de l'original
                os.system(f"python pzztool.py -c pzzu/{pzz_folder}/{pzz_file_part_name}")
                # supprime l'original
                os.remove(f"pzzu/{pzz_folder}/{pzz_file_part_name}")
        os.system("python pzztool.py -bpzz pzzu pzz2")
        verify_sha256(p_input, Path("pzz2"))
    elif args.test_check_tpl_headers:
        # Démontre que SEUL les TPLs ont ce magicnumber
        # TEST OK
        print("# TEST : CHECK TPLs HEADERS")
        for afs_data_filename in os.listdir(p_input):
            with open(p_input / afs_data_filename, "rb") as afs_data_file:
                if TPL_MAGIC_NUMBER == afs_data_file.read(4) and Path(afs_data_filename).suffix != ".tpl":
                    print(f"TPL magicfile found : afs_data.afs/{afs_data_filename}")
    elif args.test_check_decompress:
        print("# TEST : CHECK DECOMPRESS")
        os.system(f"python pzztool.py -bunpzz {args.input_path} pzzu")

        invalid_files_count = 0
        total = 0
        # check that all TPLs length is a multiple of 32
        for p in Path("pzzu").glob("**/*.tpl"):
            if p.is_file():
                #print(Path(p).stat().st_size, end=' ')
                total+=1
                if (Path(p).stat().st_size % 32) != 0:
                    print(f"Invalid TPL file length modulo 32 ({Path(p).stat().st_size % 32}) - {p}")
                    invalid_files_count += 1
        print(f"Invalid files : {invalid_files_count}/{total}")
    elif args.test_compare_position:
        # FULL_AFS_FILE_DUMP contient tous les fichiers de l'afs_data.afs et pzzu le résultat de pzztool.py -bunpzz sur l'ensemble des pzz
        # Comparaisons à effectuer :
        # pzztest.py -tcp 0 data.bin
        #     Les fichiers de l'afs_data sont parfois data2 / data3 ou absents
        # pzztest.py -tcp 2 hit.bin
        # pzztest.py -tcp 3 mot.bin
        # pzztest.py -tcp 4 _mdl.arc
        # pzztest.py -tcp 5 b_mdl.arc
        # pzztest.py -tcp 6 g_mdl.arc
        # pzztest.py -tcp 7 s_mdl.arc
        # pzztest.py -tcp 8 c_mdl.arc
        # pzztest.py -tcp 9 k_mdl.arc

        for pzzpart_path in Path("pzzu").glob("**/00"+args.input_path+"*"):
            file_path = Path("FULL_AFS_FILE_DUMP/"+pzzpart_path.parent.name+args.output_path)

            if pzzpart_path.parent.name[:2] == "pl":
                if not file_path.is_file():
                    print(f"File doesn't exist : {file_path}")
                elif pzzpart_path.stat().st_size == 0:
                    print(f"File is empty : {pzzpart_path}")
                else:
                    if not verify_sha256_2(pzzpart_path, file_path):
                        print(f"DIFFERENCE : {pzzpart_path} - {file_path}")
