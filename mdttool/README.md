# mdttool.py
Python3 script for unpack/pack MDT file format. Allow to edit texts files extracted. MIT License.

## User manual
Unpack **source_mdt.mdt** in the default new folder _source_mdt_.
If optional_dest_folder is specified we unpack in _optional_dest_folder_.
Charset has to be specified when unpacking.
```
mdttool.py --unpack source_mdt.mdt optional_dest_folder --charset EU
```
Pack **source_folder** in the default new file _source_folder.mdt_. If optional_dest_file.mdt is specified we pack in _optional_dest_file.mdt_.
```
mdttool.py --pack source_folder optional_dest_file.mdt

## Extracted file tree
In the unpacked folder we find:
* 0_N.txt - Correspond to the paragraphs block N with N starting from 0.
* conf.txt - Used for a correct repack. Don't edit this file.
* charset.tpl - The extracted TPL containing symbols textures.
