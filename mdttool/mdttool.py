#!/usr/bin/env python3
from configparser import ConfigParser
import logging
from math import ceil
from pathlib import Path


__version__ = "0.0.2"
__author__ = "rigodron, algoflash, GGLinnk, CrystalPixel"
__license__ = "MIT"
__status__ = "developpement"


# JAP charset is not implemented yet.
AVAILABLE_CHARSETS = ["USA", "EU"]
TPL_MAGIC_NUMBER = b"\x00\x20\xAF\x30"
# EU charset is shared between EN / FR / GER mdt
EU_CHARSET = { b"\x21\x21": "¡", b"\x21\x3f": "¿", b"\x21\x43": "Ç", b"\x21\x4e": "Ñ",
    b"\x21\x62": "ß", b"\x21\x63": "ç", b"\x21\x6e": "ñ", b"\x22\x41": "Ä",
    b"\x22\x45": "Ë", b"\x22\x49": "Ï", b"\x22\x4f": "Ö", b"\x22\x55": "Ü",
    b"\x22\x61": "ä", b"\x22\x65": "ë", b"\x22\x69": "ï", b"\x22\x6f": "ö",
    b"\x22\x75": "ü", b"\x27\x41": "Á", b"\x27\x45": "É", b"\x27\x49": "Í",
    b"\x27\x4f": "Ó", b"\x27\x55": "Ú", b"\x27\x61": "á", b"\x27\x65": "é",
    b"\x27\x69": "í", b"\x27\x6f": "ó", b"\x27\x75": "ú", b"\x41\x45": "Æ",
    b"\x4f\x45": "Œ", b"\x5e\x41": "Â", b"\x5e\x45": "Ê", b"\x5e\x49": "Î",
    b"\x5e\x4f": "Ô", b"\x5e\x55": "Û", b"\x5e\x61": "â", b"\x5e\x65": "ê",
    b"\x5e\x69": "î", b"\x5e\x6f": "ô", b"\x5e\x75": "û", b"\x60\x41": "À",
    b"\x60\x45": "È", b"\x60\x49": "Ì", b"\x60\x4f": "Ò", b"\x60\x55": "Ù",
    b"\x60\x61": "à", b"\x60\x65": "è", b"\x60\x69": "ì", b"\x60\x6f": "ò",
    b"\x60\x75": "ù", b"\x61\x65": "æ", b"\x6f\x65": "œ", b"\x81\x43": ",",
    b"\x81\x44": ".", b"\x81\x45": "°", b"\x81\x46": ":", b"\x81\x47": ";",
    b"\x81\x48": "?", b"\x81\x49": "!", b"\x81\x51": "_", b"\x81\x5e": "/",
    # singles and double quotes x4 (inclined in both direction)
    b"\x81\x65": None, b"\x81\x66": None, b"\x81\x67": None, b"\x81\x68": None,
    b"\x81\x69": "(", b"\x81\x6a": ")", b"\x81\x7b": "+", b"\x81\x7c": "-",
    b"\x81\x7e": "×", b"\x81\x80": "÷", b"\x81\x81": "=", b"\x81\x83": "<",
    b"\x81\x84": ">", b"\x81\x93": "%", b"\x81\x94": "#", b"\x81\x95": "&",
    b"\x81\x96": "*", b"\x81\x97": "@", b"\x81\xa5": None, b"\x82\x4f": "0",
    b"\x82\x50": "1", b"\x82\x51": "2", b"\x82\x52": "3", b"\x82\x53": "4",
    b"\x82\x54": "5", b"\x82\x55": "6", b"\x82\x56": "7", b"\x82\x57": "8",
    b"\x82\x58": "9", b"\x82\x60": "A", b"\x82\x61": "B", b"\x82\x62": "C",
    b"\x82\x63": "D", b"\x82\x64": "E", b"\x82\x65": "F", b"\x82\x66": "G",
    b"\x82\x67": "H", b"\x82\x68": "I", b"\x82\x69": "J", b"\x82\x6a": "K",
    b"\x82\x6b": "L", b"\x82\x6c": "M", b"\x82\x6d": "N", b"\x82\x6e": "O",
    b"\x82\x6f": "P", b"\x82\x70": "Q", b"\x82\x71": "R", b"\x82\x72": "S",
    b"\x82\x73": "T", b"\x82\x74": "U", b"\x82\x75": "V", b"\x82\x76": "W",
    b"\x82\x77": "X", b"\x82\x78": "Y", b"\x82\x79": "Z", b"\x82\x81": "a",
    b"\x82\x82": "b", b"\x82\x83": "c", b"\x82\x84": "d", b"\x82\x85": "e",
    b"\x82\x86": "f", b"\x82\x87": "g", b"\x82\x88": "h", b"\x82\x89": "i",
    b"\x82\x8a": "j", b"\x82\x8b": "k", b"\x82\x8c": "l", b"\x82\x8d": "m",
    b"\x82\x8e": "n", b"\x82\x8f": "o", b"\x82\x90": "p", b"\x82\x91": "q",
    b"\x82\x92": "r", b"\x82\x93": "s", b"\x82\x94": "t", b"\x82\x95": "u",
    b"\x82\x96": "v", b"\x82\x97": "w", b"\x82\x98": "x", b"\x82\x99": "y",
    b"\x82\x9a": "z"}
USA_CHARSET = { b"\x81\x43": ",", b"\x81\x44": ".", b"\x81\x45": "°", b"\x81\x46": ":",
    b"\x81\x47": ";", b"\x81\x48": "?", b"\x81\x49": "!", b"\x81\x51": "_",
    # singles and double quotes x4 (inclined in both direction)
    b"\x81\x5e": "/", b"\x81\x65": None, b"\x81\x66": None, b"\x81\x67": None,
    b"\x81\x68": None, b"\x81\x69": "(", b"\x81\x6a": ")", b"\x81\x7b": "+",
    b"\x81\x7c": "-", b"\x81\x7e": "×", b"\x81\x80": "÷", b"\x81\x81": "=",
    b"\x81\x83": "<", b"\x81\x84": ">", b"\x81\x93": "%", b"\x81\x94": "#",
    b"\x81\x95": "&", b"\x81\x96": "*", b"\x81\x97": "@", b"\x81\xa5": None,
    b"\x82\x4f": "0", b"\x82\x50": "1", b"\x82\x51": "2", b"\x82\x52": "3",
    b"\x82\x53": "4", b"\x82\x54": "5", b"\x82\x55": "6", b"\x82\x56": "7",
    b"\x82\x57": "8", b"\x82\x58": "9", b"\x82\x60": "A", b"\x82\x61": "B",
    b"\x82\x62": "C", b"\x82\x63": "D", b"\x82\x64": "E", b"\x82\x65": "F",
    b"\x82\x66": "G", b"\x82\x67": "H", b"\x82\x68": "I", b"\x82\x69": "J",
    b"\x82\x6a": "K", b"\x82\x6b": "L", b"\x82\x6c": "M", b"\x82\x6d": "N",
    b"\x82\x6e": "O", b"\x82\x6f": "P", b"\x82\x70": "Q", b"\x82\x71": "R",
    b"\x82\x72": "S", b"\x82\x73": "T", b"\x82\x74": "U", b"\x82\x75": "V",
    b"\x82\x76": "W", b"\x82\x77": "X", b"\x82\x78": "Y", b"\x82\x79": "Z",
    b"\x82\x81": "a", b"\x82\x82": "b", b"\x82\x83": "c", b"\x82\x84": "d",
    b"\x82\x85": "e", b"\x82\x86": "f", b"\x82\x87": "g", b"\x82\x88": "h",
    b"\x82\x89": "i", b"\x82\x8a": "j", b"\x82\x8b": "k", b"\x82\x8c": "l",
    b"\x82\x8d": "m", b"\x82\x8e": "n", b"\x82\x8f": "o", b"\x82\x90": "p",
    b"\x82\x91": "q", b"\x82\x92": "r", b"\x82\x93": "s", b"\x82\x94": "t",
    b"\x82\x95": "u", b"\x82\x96": "v", b"\x82\x97": "w", b"\x82\x98": "x",
    b"\x82\x99": "y", b"\x82\x9a": "z", b"\x83\xbf": None, b"\x89\xce": None,
    b"\x8c\xba": None, b"\x8c\xd5": None, b"\x8e\xe9": None, b"\x90\x9d": None,
    b"\x90\xc2": None, b"\x92\xb4": None, b"\x94\x92": None, b"\x95\x90": None,
    b"\x97\xb4": None}
# Use the next int16 without counting it in paragraph total length / max width
SPECIAL_CHARS = [b"\x80\x02", b"\x80\x03"]
# Don't use next int16
SPECIAL_CHARS_2 = [b"\x80\x00"]


# Raised during unpack when the charset is invalid.
class InvalidCharsetError(Exception): pass


def align_top(offset:int, align:int):
    """
    Give the upper rounded offset aligned using the align value.
    input: offset = int
    input: align = int
    return offset = int
    """
    if offset % align == 0: return offset
    return offset + align - (offset % align)


def bytes2_to_hex(data:bytes, skip_format=False):
    "Convert 2 bytes in hex format: \xab\xcd."
    return f"{data[0]:02x}{data[1]:02x}" if skip_format else f"\\x{data[0]:02x}\\x{data[1]:02x}"


class TxtDat:
    """
    TxtDat handle internal mdt file at position 0.
    Unpack extract data in txt files and pack join txt files back in the original format.
    """
    PARAGRAPH_SEPARATOR = "\n--------------------------------\n"
    __HEADERALIGN = 32
    __path = None
    __symbols_count = None
    # symbol list contains the positionnal symbols translated from header in16 id to ascii
    __symbol_list = None
    # first offset containing a list of paragraphs offsets blocks -1 terminated
    __paragraph_offsets_blocks_list_offset = None
    def __init__(self, path:Path):
        "input: path = path of the unpacked mdt folder."
        self.__path = path
        self.__symbol_list = []
    def unpack(self, file_data:bytes, charset:str):
        """
        Extract all paragraphs blocks in files 0_N.txt with N the block number starting from 0.
        input: file_data = total datas of the file
        input: charset = charset used into it
        """
        charset_dict = None

        if charset == "USA":
            charset_dict = USA_CHARSET
        elif charset == "EU":
            charset_dict = EU_CHARSET

        self.__paragraph_offsets_blocks_list_offset = int.from_bytes(file_data[:4], "big")
        self.__symbols_count = int.from_bytes(file_data[4:8], "big")

        conf_txt = f"{charset}"

        for i in range(self.__symbols_count):
            symbol_data = file_data[8+i*2:10+i*2]
            self.__symbol_list.append( charset_dict[symbol_data] )
            conf_txt += ";" + bytes2_to_hex(symbol_data, skip_format=True)

        # conf store the charset used and the symbols id list in ascii.
        (self.__path / "conf.txt").write_text(conf_txt)

        # First we iterate in the paragraph offsets blocks list.
        # paragraph offset blocks list contains a list of offsets that point on paragraphs offsets blocks -1 terminated.
        # each extracted paragraph offset correspond to a 0_N.txt file.
        i = 0
        while True:
            paragraph_offsets_block_offset = int.from_bytes(file_data[self.__paragraph_offsets_blocks_list_offset + i*4:self.__paragraph_offsets_blocks_list_offset + 4 + i*4], "big", signed=True)
            if paragraph_offsets_block_offset == -1:
                break
            # Then we walk the paragraphs offset list for extracting texts from this block - also -1 terminated. 
            j = 0
            paragraphs_txt = ""
            while True:
                paragraph_offset = int.from_bytes(file_data[paragraph_offsets_block_offset + j*4:paragraph_offsets_block_offset + j*4 + 4], "big", signed=True)
                if paragraph_offset == -1:
                    paragraphs_txt = paragraphs_txt[:-len(TxtDat.PARAGRAPH_SEPARATOR)]
                    break

                # int16 = total uint16 len without special chars values counted in it.
                paragraph_len = int.from_bytes(file_data[paragraph_offset:paragraph_offset+2], "big")
                # Paragraph line count int16 2:4 and max width int16 4:6 are ignored and can be deduced from the paragraph when packing back txt files.
                # Now we extract paragraph and translate it in txt format. Special values and values not present in charset are translated in \xaa\xbb txt format.
                k = 3
                while k < paragraph_len + 3:
                    char_data = file_data[paragraph_offset + k*2:paragraph_offset + k*2 + 2]
                    char_value = int.from_bytes(char_data, "big", signed=True)

                    if 0 <= char_value < self.__symbols_count and self.__symbol_list[char_value] is not None:
                        paragraphs_txt += self.__symbol_list[char_value]
                    elif char_value == -2:
                        paragraphs_txt += " "
                    elif char_data == b"\x10\x00":
                        paragraphs_txt += "\n"
                    else:
                        paragraphs_txt += bytes2_to_hex(char_data)
                        if char_data in SPECIAL_CHARS:
                            paragraph_len += 2
                            paragraphs_txt += bytes2_to_hex(file_data[paragraph_offset + k*2 + 2:paragraph_offset + k*2 + 4])
                            k += 2
                            continue
                        elif char_data in SPECIAL_CHARS_2:
                            paragraph_len += 1
                    k += 1
                paragraphs_txt += TxtDat.PARAGRAPH_SEPARATOR
                j += 1
            (self.__path / f"0_{i}.txt").write_text(paragraphs_txt)
            i += 1
    def pack(self, files_paths:Path):
        """
        Pack parse 0_N.txt files and create back the original file format packed in position 0 of the mdt.
        input: files_paths = paths of all txts to pack.
        return the raw datas of repacked files.
        """
        conf_txt = (self.__path / "conf.txt").read_text().split(";")
        charset_dict = None
        if conf_txt[0] == "USA":
            charset_dict = USA_CHARSET
        elif conf_txt[0] == "EU":
            charset_dict = EU_CHARSET

        self.__symbols_count = 0
        header_bytes = b""

        # First we parse conf and retrieve our charset in the right order.
        for symbol_data in conf_txt[1:]:
            self.__symbols_count += 1
            symbol_data_b = bytes.fromhex(symbol_data)
            self.__symbol_list.append( charset_dict[symbol_data_b] )
            header_bytes += symbol_data_b
        
        header_bytes = self.__symbols_count.to_bytes(4, "big") + header_bytes

        # We align header with 32 mores bytes if we have the exact match of align.
        header_bytes = header_bytes.ljust( len(header_bytes) + TxtDat.__HEADERALIGN - ( (len(header_bytes) + 4) % TxtDat.__HEADERALIGN), b"\x00" )
        header_bytes = (len(header_bytes) + 4).to_bytes(4, "big") + header_bytes

        # Now we retrieve every paragraph of the unpacked folder files and we translate it back to bytes with 32 bytes align.
        # Each file correspond to a paragraph offset block list & corresponding paragraphs.
        paragraphs_list = []
        for file_path in files_paths:
            paragraphs = []
            for paragraph_txt in file_path.read_text().split(TxtDat.PARAGRAPH_SEPARATOR):
                paragraph = b""
                
                # first 6 bytes contains total paragraph len uint16 in symbols, lines count int16 and max width int16 in symbols including \n
                total_len = 0
                max_width = 0
                i = 0
                current_width = 0
                while i < len(paragraph_txt):
                    if paragraph_txt[i:i+2] == "\\x":
                        paragraph += bytes.fromhex(paragraph_txt[i+2:i+4] + paragraph_txt[i+6:i+8])
                        if bytes.fromhex(paragraph_txt[i+2:i+4] + paragraph_txt[i+6:i+8]) in SPECIAL_CHARS:
                            current_width -= 1
                            total_len -= 1
                        elif bytes.fromhex(paragraph_txt[i+2:i+4] + paragraph_txt[i+6:i+8]) not in SPECIAL_CHARS_2:
                            total_len += 1
                            current_width += 1
                        i += 8
                        continue
                    elif paragraph_txt[i] == "\n":
                        max_width = max(max_width, current_width + 1)
                        paragraph += b"\x10\x00"
                        current_width = -1 # to 0
                    elif paragraph_txt[i] == ' ':
                        paragraph += b"\xFF\xFE"
                    else:
                        paragraph += self.__symbol_list.index(paragraph_txt[i]).to_bytes(2, "big")
                    total_len += 1
                    current_width += 1
                    i += 1
                max_width = max(max_width, current_width)
                
                paragraph = total_len.to_bytes(2, "big") + len(paragraph_txt.splitlines()).to_bytes(2, "big") + max_width.to_bytes(2, "big") + paragraph
                paragraphs.append( paragraph.ljust(align_top(len(paragraph), 32), b"\x00") )
            paragraphs_list.append(paragraphs)

        # header_bytes contains the header aligned to 32 upper
        # Here we align to 32 the paragraph_offsets_blocks_list
        current_offset = len(header_bytes) + align_top(len(paragraphs_list)*4 + 4, 32) # + 4 because -1 terminated
        body_data = b""
        # for each paragraphs offsets block offset we add it at the end of header for paragraphs offets block list
        for paragraphs in paragraphs_list:
            header_bytes += current_offset.to_bytes(4, "big")
            # We calculate end of paragraph_offsets_block before adding paragraphs content in data block following it.
            current_offset += align_top(len(paragraphs)*4 + 4, 32) # -1 terminated

            offsets_block = b""
            data_block = b""
            for paragraph in paragraphs:
                offsets_block += current_offset.to_bytes(4, "big")
                data_block += paragraph
                # each paragraph is already aligned to 32
                current_offset += len(paragraph)

            offsets_block += b"\xFF\xFF\xFF\xFF"
            offsets_block = offsets_block.ljust(align_top(len(offsets_block), 32), b"\x00")
            body_data += offsets_block + data_block

        header_bytes += b"\xFF\xFF\xFF\xFF"
        header_bytes = header_bytes.ljust(align_top(len(header_bytes), 32), b"\x00")

        return header_bytes + body_data


class Mdt:
    "Unpack and pack files in the mdt with 0x800 bytes header and files aligned to 0x800 with padding."
    __HEADER_LEN = 0x800
    __ALIGN = 0x800
    def unpack(self, mdt_path:Path, folder_path:Path, charset:str):
        "Unpack extract the charset tpl and unpack the first file into txt files using TxtDat."
        logging.info(f"Unpacking {mdt_path} in {folder_path}...")
        
        with mdt_path.open("rb") as mdt_file:
            file_count = int.from_bytes(mdt_file.read(4), "big")
            file_length_list = []
            for i in range(file_count):
                file_length_list.append( int.from_bytes(mdt_file.read(4), "big") * Mdt.__ALIGN )
            
            mdt_file.seek(Mdt.__HEADER_LEN)

            folder_path.mkdir()

            if len(file_length_list) != 2:
                raise Exception("Error - mdt total files != 2!")

            txtdat = TxtDat(folder_path)
            txtdat.unpack( mdt_file.read(file_length_list[0]), charset)
            
            (folder_path / "charset.tpl").write_bytes( mdt_file.read(file_length_list[1]) )
    def pack(self, folder_path:Path, mdt_path:Path):
        "Pack group the charset tpl and the first file data into the mdt using TxtDat to get the first file right format."
        logging.info(f"Packing {folder_path} in {mdt_path}...")
        
        txtdat = TxtDat(folder_path)
        dat_files_paths = list(folder_path.glob("0_*"))
        txtdat_data = txtdat.pack(dat_files_paths)

        with mdt_path.open("wb") as mdt_file:
            header_bytes = b"\x00\x00\x00\x02"
            
            mdt_file.seek(Mdt.__HEADER_LEN)
            header_bytes += ceil(len(txtdat_data) / Mdt.__ALIGN).to_bytes(4, "big")
            mdt_file.write( txtdat_data.ljust(align_top(len(txtdat_data), self.__ALIGN), b"\x00") )

            file_data = (folder_path / "charset.tpl").read_bytes()
            header_bytes += ceil(len(file_data) / Mdt.__ALIGN).to_bytes(4, "big")
            mdt_file.write(file_data)

            mdt_file.seek(0)
            mdt_file.write( header_bytes )


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='Gotcha Force MDT packer & unpacker - [GameCube] v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-c', '--charset', type=str, help='-c=USA: use USA charset when unpacking.', default="")
    parser.add_argument('input_path', metavar='INPUT', help='')
    parser.add_argument('output_path', metavar='OUTPUT', help='', nargs='?', default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack', action='store_true', help="-p source_folder (dest_file.mdt): Pack source_folder in new file source_folder.mdt or dest_file.mdt if specified.")
    group.add_argument('-u', '--unpack', action='store_true', help="-u source_file.mdt (dest_folder): Unpack the mdt file in new folder source_file or dest_folder if specified.")
    return parser


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    args = get_argparser().parse_args()

    p_input = Path(args.input_path)
    p_output = Path(args.output_path)

    mdt = Mdt()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.pack:
        logging.info("### Pack")
        if not p_input.is_dir():
            raise Exception("Error - Invalid unpacked mdt folder path.")

        if p_output == Path("."):
            p_output = p_input.with_suffix(".mdt")

        if p_output.is_file() or p_output.is_dir():
            raise Exception(f"Error - {p_output} already exist. Please remove it before packing.")

        mdt.pack(p_input, p_output)
    elif args.unpack:
        logging.info("### Unpack")
        if args.charset not in AVAILABLE_CHARSETS:
            raise InvalidCharsetError(f"Error - Invalid charset. To unpack the charset must be specified and in {str(AVAILABLE_CHARSETS)}")
        
        if not p_input.is_file():
            raise Exception("Error - Invalid mdt file path.")

        if p_output == Path("."):
            p_output = p_input.parent / p_input.stem

        if p_output.is_file() or p_output.is_dir():
            raise Exception(f"Error - {p_output} already exist. Please remove it before unpacking.")

        mdt.unpack(p_input, p_output, args.charset)
