# NeoGF
NeoGF is a library of tools for Gotcha Force.

> This project is still under "heavy" development. It not yet 100% ready to use.
> 
> Do not hesitate to contribute.

If you want more infos about the game, go read our [Gotcha Force Wiki](http://re.wiki.virtualworld.fr/index.php/Gotcha_Force).

## gcmtool.py
Python3 script for unpack/pack GCM iso files. This tool can rebuild FileStringTable (FST) of GCM and patch boot.bin with a new apploader.img, boot.dol, add/remove/edit of folder and files of the game.

### User manual
Unpack iso GCM file **game.iso** in folder **iso_extract**: (If the destination folder is not specified, it will use the game_code-DVD_number as folder.)
```
gcmtool.py -u game.iso iso_extract
```
Pack folder in iso :
```
gcmtool.py -p iso_extract game.iso
```
Rebuild FST and patch boot.bin for a new apploader, dol, and add/remove/edit of folders and files :
```
gcmtool.py -r iso_extract
```
Japanese charset is not handled for now. The original GCM iso and repack GCM iso are different most of the time. This is because GCM DVD contains "empty spaces" with data unused (old datas or random datas I don't know). So this datas are useless and loss during unpack.

### Extracted file tree
root folder contains all files of the extracted GCM iso

sys folder contains GCM system files of the game :
* boot.bin
* bi2.bin
* apploader.img
* boot.dol
* fst.bin

## pzztool.py
Python3 script for unpack/repack unpzz/pzz and uncompress/compress of PZZ archive. MDT files are also handled by pzztool.py.

### How to patch a pzz
1. Extract afs_data.afs from the ROM
2. Extract the pzz file from afs_data.afs
3. unpzz it
6. Edit files in decompressed folder keeping the filename important parts inchanged (see "Extracted files format" for further informations)
7. pzz the decompressed folder
8. Import back the patched pzz in the afs_data.afs
9. Patch the ROM with new afs_data.afs

### User manual
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

### Extracted files format
Every file extracted has a name using the format :

AAAB_C.D
- **AAA** is the 3 digits index of the file in the PZZ starting at 000.
- **B** describe the compression state of the file when packed in the PZZ. If compressed it's **C** and if not it's **U**.
- **C** is the name of the PZZ.
- **D** is the extension of the file. If the file is compressed it's **.pzzp** (PZZ Part) and if the file is uncompressed by default it's **.dat**

For example file **012C_cmn_data.dat** describe :
- the 13th file off the pzz,
- initialy compressed,
- in a pzz named "cmn_data.pzz",
- that has been uncompressed,
- with the default format "dat".

The names of unpacked files and the presence of empty unpacked files are important to keep informations relative to the initial pzz and ensure a correct pack.
