# mottool.py
Python3 script for unpack/pack MOT file format. Currently under development. Unit tests are not implemented yet. MIT License.

## User manual
Unpack **source_mot.bin** in the default new folder _source_mot_.
If optional_dest_folder is specified we unpack in _optional_dest_folder_. Not fully implemented yet.
```
mottool.py --unpack source_mot.bin optional_dest_folder
```
Pack **source_folder** in the default new file _source_folder.bin_. If optional_dest_file.bin is specified we pack in _optional_dest_file.bin_. Not implemented yet.
```
mottool.py --pack source_folder optional_dest_file.bin
```
