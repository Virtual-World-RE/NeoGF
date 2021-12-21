#!/usr/bin/env python3
from pathlib import Path
import logging


__version__ = "0.0.3"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


DVD_MAGIC = b"\xC2\x33\x9F\x3D"
FST_TYPE_FILE = 0
FST_TYPE_DIR = 1


######################################################################
# Todo : add extension check ; add --disable-ignore
# -> test it on random iso and check that it's the same than dolphin extract
# -> test it !!!!
# Add FST rebuild ;
# add info on unused randoms bytes on initial DVD iso file
# -> that's why repack iso is different from initial iso
######################################################################
class Dol:
    # Get total length using the sum of the 18 sections length and dol header length (0x100)
    def getDolLen(self, dolheader_data:bytes):
        dol_len = 0x100
        for i in range(18):
            dol_len += int.from_bytes(dolheader_data[0x90+i*4:0x90+(i+1)*4], "big", signed=False)
        return dol_len


# https://sudonull.com/post/68549-Gamecube-file-system-device
class GCM:
    def unpack(self, iso_path:Path, folder_path:Path):
        with iso_path.open("rb") as iso_file:
            bootbin_data = iso_file.read(0x440)
            if bootbin_data[0x1c:0x20] != DVD_MAGIC:
                raise Exception("Invalid DVD format - this tool is for ISO/GCM files")
            bi2bin_data = iso_file.read(0x2000)

            # https://www.gc-forever.com/wiki/index.php?title=Apploader
            # -> Full apploader size is sum of size and trailerSize, rounded up to 32 bytes.
            iso_file.seek(0x2454)
            size = int.from_bytes(iso_file.read(4), "big", signed=False)
            trailerSize = int.from_bytes(iso_file.read(4), "big", signed=False)
            
            # Dolphin Emulator add 32 Null bytes at the end of the extracted apploader.img
            apploader_size = size + trailerSize + 32
            
            iso_file.seek(0x2440)
            apploaderimg_data = iso_file.read(apploader_size)

            fstbin_offset = int.from_bytes(bootbin_data[0x424:0x428],"big", signed=False)
            fstbin_len = int.from_bytes(bootbin_data[0x428:0x42c],"big", signed=False)
            iso_file.seek( fstbin_offset )
            fstbin_data = iso_file.read( fstbin_len )

            dol_offset = int.from_bytes(bootbin_data[0x420:0x424],"big", signed=False)
            iso_file.seek( dol_offset )
            dol = Dol()
            dolheader_data = iso_file.read(0x100)
            dol_len = dol.getDolLen( dolheader_data )
            bootdol_data = dolheader_data + iso_file.read( dol_len - 0x100 )
            if folder_path != Path("."):
                base_path = folder_path
            else:
                base_path = Path(f"{bootbin_data[:4].decode('utf-8')}-{int.from_bytes(bootbin_data[6:7], 'little', signed=False):02}")
            
            logging.info(f"unpacking {iso_path} in {base_path}")
            sys_path = base_path / "sys"
            sys_path.mkdir(parents=True, exist_ok=True)

            with (sys_path / "boot.bin").open("wb") as bootbin_file, \
                 (sys_path / "bi2.bin" ).open("wb") as bi2bin_file, \
                 (sys_path / "fst.bin").open("wb") as fstbin_file, \
                 (sys_path / "apploader.img").open("wb") as apploaderimg_file,\
                 (sys_path / "boot.dol").open("wb") as bootdol_file:
                logging.debug(f"{iso_path}(0x0:0x440) -> {sys_path / 'boot.bin'}")
                bootbin_file.write(bootbin_data)
                logging.debug(f"{iso_path}(0x440:0x2440) -> {sys_path / 'bi2.bin'}")
                bi2bin_file.write(bi2bin_data)
                logging.debug(f"{iso_path}(0x2440:0x{0x2440 + apploader_size:x} -> {sys_path / 'apploader.img'}")
                apploaderimg_file.write(apploaderimg_data)
                logging.debug(f"{iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x}) -> {sys_path / 'fst.bin'}")
                fstbin_file.write(fstbin_data)
                logging.debug(f"{iso_path}(0x{dol_offset:x}:0x{dol_offset + dol_len:x}) -> {sys_path / 'boot.dol'}")
                bootdol_file.write(bootdol_data)
            root_path = base_path / "root"
            root_path.mkdir(exist_ok=True)
            
            # And now we parse FST data to unpack all files in the GCM iso file
            dir_index_path = {0: root_path}
            currentdir_path = root_path

            # root: index=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when index reach next dir
            nextdir_arr = [ nextdir ]

            for index in range(1, base_names // 12):
                i = index * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                
                while index == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FST_TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_index_path[parentdir] / name
                    dir_index_path[index] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    with (currentdir_path / name).open("wb") as new_file:
                        iso_file.seek(fileoffset)
                        new_file.write( iso_file.read(filesize) )

                        logging.debug(f"{iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x}) -> {currentdir_path / name}")
    def pack(self, folder_path:Path, iso_path:Path = None):
        if iso_path == None:
            iso_path = folder_path.parent / Path(folder_path.name).with_suffix(".iso")
        with iso_path.open("wb") as iso_file, \
             (folder_path / "sys" / "boot.bin").open("rb") as bootbin_file, \
             (folder_path / "sys" / "bi2.bin" ).open("rb") as bi2bin_file, \
             (folder_path / "sys" / "fst.bin").open("rb") as fstbin_file, \
             (folder_path / "sys" / "apploader.img").open("rb") as apploaderimg_file,\
             (folder_path / "sys" / "boot.dol").open("rb") as bootdol_file :

            logging.debug(f"{folder_path / 'sys' / 'boot.bin'}      -> {iso_path}(0x0:0x440)")
            logging.debug(f"{folder_path / 'sys' / 'bi2.bin'}       -> {iso_path}(0x440:0x2440)")
            logging.debug(f"{folder_path / 'sys' / 'apploader.img'} -> {iso_path}(0x2440:0x{0x2440 + (folder_path / 'sys' / 'apploader.img').stat().st_size:x}")
            
            bootbin_data = bootbin_file.read()
            iso_file.write( bootbin_data )
            iso_file.write(bi2bin_file.read())
            iso_file.write(apploaderimg_file.read())

            fstbin_offset = int.from_bytes(bootbin_data[0x424:0x428],"big", signed=False)
            fstbin_len = int.from_bytes(bootbin_data[0x428:0x42c],"big", signed=False)
            if (folder_path / "sys" / "fst.bin").stat().st_size != fstbin_len:
                raise Exception("Invalid fst.bin size in boot.bin offset 0x428:0x42c!")
            logging.debug(f"{folder_path / 'sys' / 'fst.bin'}       -> {iso_path}(0x{fstbin_offset:x}:0x{fstbin_offset + fstbin_len:x})")
            iso_file.seek( fstbin_offset )
            fstbin_data = fstbin_file.read()
            iso_file.write( fstbin_data )
            
            dol_offset = int.from_bytes(bootbin_data[0x420:0x424],"big", signed=False)
            logging.debug(f"{folder_path / 'sys' / 'boot.dol'}      -> {iso_path}(0x{dol_offset:x}:0x{dol_offset + (folder_path / 'sys' / 'boot.dol').stat().st_size:x})")
            iso_file.seek( dol_offset )
            iso_file.write( bootdol_file.read() )

            # Now parse fst.bin for writing files in the iso
            dir_index_path = {0: folder_path / "root"}
            currentdir_path = folder_path / "root"

            # root: index=0 so nextdir is the end
            nextdir = int.from_bytes(fstbin_data[8:12], "big", signed=False)
            # offset of filenames block
            base_names = nextdir * 12
            # go to parent when index reach next dir
            nextdir_arr = [ nextdir ]

            for index in range(1, base_names // 12):
                i = index * 12
                file_type = int.from_bytes(fstbin_data[i:i+1], "big", signed=False)
                name = fstbin_data[base_names + int.from_bytes(fstbin_data[i+1:i+4], "big", signed=False):].split(b"\x00")[0].decode("utf-8")
                
                while index == nextdir_arr[-1]:
                    currentdir_path = currentdir_path.parent
                    nextdir_arr.pop()

                if file_type == FST_TYPE_DIR:
                    nextdir = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)
                    parentdir = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)

                    nextdir_arr.append( nextdir )
                    currentdir_path = dir_index_path[parentdir] / name
                    dir_index_path[index] = currentdir_path
                    currentdir_path.mkdir(exist_ok=True)
                else:
                    fileoffset = int.from_bytes(fstbin_data[i+4:i+8], "big", signed=False)
                    filesize   = int.from_bytes(fstbin_data[i+8:i+12], "big", signed=False)

                    with (currentdir_path / name).open("rb") as new_file:
                        logging.debug(f"{currentdir_path / name} -> {iso_path}(0x{fileoffset:x}:0x{fileoffset + filesize:x})")
                        iso_file.seek(fileoffset)
                        iso_file.write( new_file.read(filesize) )


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='ISO/GCM packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('input_path',  metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack',   action='store_true', help="-p source_folder (dest_file.iso) : Pack source_folder in new file source_folder.iso or dest_file.iso if specified")
    group.add_argument('-u', '--unpack', action='store_true', help='-u source_iso.iso (dest_folder) : Unpack the GCM/ISO in new folder source_iso or dest_folder if specified')
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    gcm = GCM()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        logging.info("### Pack")
        if(p_output == Path(".")):
            p_output = Path(p_input.with_suffix(".iso"))
        logging.info(f"packing folder {p_input} in {p_output}")
        gcm.pack( p_input, p_output )
    elif args.unpack:
        logging.info("### Unpack")
        gcm.unpack( p_input, p_output )
