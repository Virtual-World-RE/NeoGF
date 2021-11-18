import argparse
import pzztool
import hashlib
import os


def argparser():
    parser = argparse.ArgumentParser(description='TEST TOOL')
    parser.add_argument('input_path',  metavar='INPUT',  help='')
    return parser.parse_args()


if __name__ == '__main__':
    listofinvalid = []
    args = argparser()

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
    
    """
        Code pour le developement --> pzztool.py -a a
        compare le sha256 de chaque PZZ du dossier pzz et pzz2 puis affiche le nom de fichier en cas de différence
    import hashlib
    for pzz_file in listdir("pzz"):
        with open("pzz/"+pzz_file, "rb") as f1, open("pzz2/"+pzz_file, "rb") as f2:
            if hashlib.sha256( f1.read() ).hexdigest() != hashlib.sha256( f2.read() ).hexdigest() :
                print(pzz_file)
    """
