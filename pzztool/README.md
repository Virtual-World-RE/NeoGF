# pzztool.py
Python3 script for unpack/repack unpzz/pzz and uncompress/compress of PZZ archive. Handle also ARZ files decompression. MIT License.

## How to patch a pzz
1. Extract afs_data.afs from the ROM
2. Extract the pzz file from afs_data.afs
3. unpzz it
6. Edit files in decompressed folder keeping the filename important parts inchanged (see "Extracted files format" for further informations)
7. pzz the decompressed folder
8. Import back the patched pzz in the afs_data.afs
9. Patch the ROM with new afs_data.afs

## User manual
unpzz **source.pzz** in the default new folder _source_.
If optional_dest_folder is specified we unpack in _optional_dest_folder_.
unpzz handle auto-decompress of all files extracted.
```
pzztool.py -unpzz source.pzz optional_dest_folder
```
pzz **source_folder** in the default new pzz file _source_folder.pzz_.
If optional_dest.pzz is specified we pzz in _optional_dest.pzz_.
pzz handle auto-compress / auto-decompress of all files extracted from the pzz according to their initial states in the pzz.
```
pzztool.py -pzz source_folder optional_dest.pzz
```
unpzz every pzz files present in _source_folder_ using the same directory.
For each pzz a folder is created using the name of the pzz.
If optional_dest_folder is specified we unpzz all files in _optional_dest_folder_ instead of source_folder.
The batch pzz command could be very time consuming (1h30 for whole pzz in afs_data).
```
pzztool.py -bunpzz source_folder optional_dest_folder
```
pzz every folder present in _source_folder_ using the same directory.
For each folder a pzz file is created using the name of the pzz.
If optional_dest_folder is specified we pzz all folders in _optional_dest_folder_ instead of source_folder.
The batch pzz command could be very time consuming (1h30 for whole pzz in afs_data).
```
pzztool.py -bpzz source_folder optional_dest_folder
```
Unpack **source.pzz** in the default new folder _source_.
If optional_dest_folder is specified we unpack in _optional_dest_folder_.
This is faster than unpzz but compression must be handled by user after the unpack.
```
pzztool.py -u source.pzz optional_dest_folder
```
Pack **source_folder** in the default new pzz file _source_folder.pzz_.
If optional_dest.pzz is specified we pack in _optional_dest.pzz_.
This is faster than pzz but compression must be handled by user before the pack.
```
pzztool.py -p source_folder optional_dest.pzz
```
Unpack every pzz files present in _source_folder_ using the same directory.
For each pzz a folder is created using the name of the pzz.
If optional_dest_folder is specified we unpack all files in _optional_dest_folder_ instead of source_folder.
```
pzztool.py -bu source_folder optional_dest_folder
```
Pack every folder present in _source_folder_ using the same directory.
For each folder a pzz file is created using the name of the pzz.
If optional_dest_folder is specified we pack all folders in _optional_dest_folder_ instead of source_folder.
```
pzztool.py -bp source_folder optional_dest_folder
```

## Extracted files format
Every file extracted has a name using the format:

AAAB_CD.D
- **AAA** is the 3 digits index of the file in the PZZ starting at 000.
- **B** describe the compression state of the file when packed in the PZZ. If compressed it's **C** and if not it's **U**.
- **C** is the name of the PZZ.
- **D** is the resolved name and extension of the file. If the file is compressed it use the **.pzzp** (PZZ Part) extension and if the file is uncompressed by default it's **.dat**

For example file **012C_cmn_data.dat** describe:
- the 13th file off the pzz,
- initialy compressed,
- in a pzz named "cmn_data.pzz",
- that has been uncompressed,
- with the default format "dat".

The names of unpacked files and the presence of empty unpacked files are important to keep informations relative to the initial pzz and ensure a correct pack.
