import argparse
from pathlib import Path
import pzztool
import hashlib
import os


TPL_MAGIC_FILE = b"\x00\x20\xAF\x30" # http://virtualre.rf.gd/index.php/TPL_(Format_de_fichier)

def get_argparser():
    parser = argparse.ArgumentParser(description='TEST TOOL')
    parser.add_argument('input_path',  metavar='INPUT',  help='')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-tdc',  '--test-decompress-compress',  action='store_true', help="")
    group.add_argument('-tbup', '--test-batch-unpack-pack',    action='store_true', help="""
        -tbup source_pzz_folder
        source_pzz_folder  : put all pzz in this folder
        pzzu : will be created with all unpacked pzz from pzz folder
        pzz2 : will be created with all packed pzz from pzzu folder
        then it will print the file name when file sha256 is different between source_pzz_folder and pzz2 folder""")
    group.add_argument('-tctplh', '--test-check-tpl-headers',   action='store_true', help="-tctplh afs_data_folder : check all files headers in the afs_data and print those who have the tpl magicfile")
    group.add_argument('-td', '--test-decompress',              action='store_true', help="""
        pzz : put all pzz in this folder
        then tip "pzztool.py -td"
        decompressed_tpl_files : will be created with all decompressed files from pzzu having the tpl header
        The script will then check that tpls are correctly decompressed with their specific characteristics""")

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
        # compare le sha256 de chaque PZZ du dossier passé en argument et pzz2 puis affiche le nom de fichier en cas de différence
        print("# TEST : BATCH UNPACK PACK")
        os.system(f"python pzztool.py -bu {args.input_path} pzzu -v")
        os.system("python pzztool.py -bp pzzu pzz2 -v")

        invalid_files_count = 0
        for pzz_file_name in os.listdir(p_input):
            with open(p_input / pzz_file_name, "rb") as f1, open(f"pzz2/{pzz_file_name}", "rb") as f2:
                if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
                    print(f"ERROR - INVALID FILE : {pzz_file_name}")
                    invalid_files_count +=1
        print(f"Invalid files : {invalid_files_count}/{len(os.listdir(p_input))}")
    elif args.test_check_tpl_headers:
        # Démontre que SEUL les TPLs ont ce magicfile
        # TEST OK
        print("# TEST : CHECK TPLs HEADERS")
        for afs_data_filename in os.listdir(p_input):
            with open(p_input / afs_data_filename, "rb") as afs_data_file:
                if TPL_MAGIC_FILE == afs_data_file.read(4) and Path(afs_data_filename).suffix != ".tpl":
                    print(f"TPL magicfile found : afs_data.afs/{afs_data_filename}")
    elif args.test_check_decompress:
        print("# TEST : CHECK DECOMPRESS")
        # create decompressed_tpl_files folder
        # copy pzzu files having the tpl header inside decompressed_tpl_files
        # check that the length is a multiple of 32
 
