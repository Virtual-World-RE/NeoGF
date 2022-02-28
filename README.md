# NeoGF
NeoGF is a library of tools for GameCube and Gotcha Force.

> This project is still under "heavy" development. It not yet 100% ready to use.
> 
> Do not hesitate to contribute.

If you want more infos about the game, go read our [Gotcha Force Wiki](http://re.wiki.virtualworld.fr/index.php/Gotcha_Force).

**Warning - Running tests is for dev purpose: it will create lots of files and this could stress your SSD.**

## gcmtool.py
Python3 script for unpack/pack/rebuild GCM/iso file format. This tool can rebuild FileStringTable (FST) of GCM and patch boot.bin with a new apploader.img, boot.dol, add/remove/edit folder and files of the game.

### User manual
Unpack GCM/iso file **source_gcm.iso** in the default new folder _game_code-DVD_number_. If optional_dest_folder is specified we unpack in _optional_dest_folder_.
```
gcmtool.py --unpack source_gcm.iso optional_dest_folder
```

Pack **source_folder** in the default new GCM/iso file _source_folder.iso_. If optional_dest_file.iso is specified we pack in _optional_dest_file.iso_. If one of the files or system files contains length change we have to use --rebuild-fst command before packing.
```
gcmtool.py --pack source_folder optional_dest_file.iso
```
Rebuild the FST file system of an unpacked GCM/iso and patch boot.bin for a new apploader, dol, and add/remove/edit of folders and files.
```
gcmtool.py --rebuild-fst source_folder
```
Print stats about the GCM/iso file or the unpacked GCM/iso folder. This stats contains informations about full memory mapping sorted by offset (files and system files), get empty spaces informations using optional align -a (default=4).
```
gcmtool.py --stats path -a 4 
```
Japanese charset is not handled for now except if you have installed Japanese local. The original GCM/iso and repack GCM/iso are different most of the time. This is because GCM DVD contains "empty spaces" with data unused (old datas or random datas I don't know). So this datas are useless and loss during unpack. The sorting of files during FST rebuild is deferent from the original and this is full compatible with the GameCube dol API.

### Extracted file tree
root folder contains all files of the unpacked GCM/iso

sys folder contains GCM system files of the game:
* boot.bin
* bi2.bin
* apploader.img
* boot.dol
* fst.bin

## afstool.py
Python3 script for unpack/pack/rebuild AFS file format. Rebuild of Table of content (TOC) and Filename directory (FD) is possible with full controll of every parameters.

### User manual
Unpack **source_afs.afs** in the default new folder _source_afs_.
If optional_dest_folder is specified we unpack in _optional_dest_folder_.
If the FD is present we use OS mtime to store the date of the file.
```
afstool.py --unpack source_afs.afs optional_dest_folder
```
Pack **source_folder** in the default new file _source_folder.afs_. If optional_dest_file.afs is specified we pack in _optional_dest_file.afs_. If the FD is present we use OS mtime to retrieve and update the date of the file. Pack handle max file size using next file (or sys file) offset. Without FD the last file has no max length constraint. FD Names stay inchanged by the pack command.
```
afstool.py --pack source_folder optional_dest_file.afs
```
Rebuild the AFS file system of an unpacked AFS using afs_rebuild.conf and afs_rebuild.csv. See afs_rebuild.conf below for more informations.
```
afstool.py --rebuild source_folder
```
Print stats about the AFS file or the unpacked AFS folder. Get full informations about header, TOC, FD, full memory mapping sorted by offsets (files and sys files), addresses space informations, and duplicated filenames grouped by filenames.
```
afstool.py --stats path
```

### Extracted file tree
**root** folder contains all files of the unpacked AFS

**sys** folder contains AFS system files and generated files needed for AFS operations:
* tableofcontent.bin - TOC sys file: You can edit this file it will be handled by the --pack command.
* filenamedirectory.bin - FD sys file: This file is created only if there is a FD in the AFS.
* filename_resolver.csv - Created when multiple files have the same name in the FD.
* afs_rebuild.conf - Edit this file for rebuilding the AFS.
* afs_rebuild.csv - Edit this file according to the configuration used in afs_rebuild.conf for rebuilding the AFS.

### filename_resolver.csv
When there is a FD with duplicated filenames, extracted files with duplicated names use "filename **(N)**.ext" with N:Integer. Pack doesn't change the FD filenames. This file is used to match unpacked_filenames to an index in the TOC/FD during pack keeping the original name.

Each lines of this csv contains a couple of "index/unpacked_filename". If there is no FD in the AFS, files are named with their index, for instance: "00000000" for the first file. You can use the resolver to rename unpacked files using the TOC index like this: "0/my_new_filename.ext". Then during pack afstool.py will auto detect the unpacked_file and put it at the right index.

### afs_rebuild.conf
All offsets and indexes are stored in hexadecimal with 0x prefix: 0xabcdef. Use auto when it's possible.

#### \[Default\] section
**AFS_MAGIC**: 0x41465300 or 0x41465320

**files_rebuild_strategy**: auto, index, offset or mixed

files_rebuild_strategy is used to organise files (indexes, offsets, packed name if there is a FD) in AFS. The strategy use informations in **afs_rebuild.csv** autogenerated during unpack. 4 strategies are available:
* auto: Rebuild all files indexes and offsets with packed packed_filename if there is a FD or else unpacked_filename. afs_rebuild.csv indexes and offsets will be ignored.
* index: Keep the specified index for designated files. afs_rebuild.csv offsets will be ignored.
* offset: Keep the specified offset for designated files. afs_rebuild.csv indexes will be ignored.
* mixed: Keep the specified offset and index for afs_rebuild.csv entries where a value is specified.

**filename_directory**: True when there is a FD and False when there is none. If set to True then it must have a \[FilenameDirectory\] section.

#### \[FilenameDirectory\] section
**toc_offset_of_fd_offset**: The TOC offset of the FD offset is at the end of the TOC. Some AFS use pad after the offsets/lengths serie. Use auto when it's possible.

**fd_offset**: The FD is at the end of the AFS. Use auto when it's possible.

**fd_last_attribute_type**: The type of the last 4 bytes of each FD entries. 4 values are available:
* length: Use file length.
* offset-length: Use offset length series.
* 0xabcdef: Use a custom hexadecimal constant.
* unknown: Don't know yet what it represent.

### afs_rebuild.csv
afs_rebuild.csv contains entries describing how to pack files in the AFS. All offsets and indexes are stored in hexadecimal with 0x prefix: 0xabcdef. Use auto for offsets or indexes when it's possible. Offsets have to be aligned to 0x800 (2048). Put one line per selected file that you wan't to constraint using the format: "unpacked_filename/index/offset/packed_filename", for instance: "dummy (5).bin/0x12/0x80000/dummy.bin". You can put auto to index or offset: "dummy (5).bin/auto/auto/dummy.bin". For an empty block add only offset/length couple with values aligned to 0x800, for instance: "0x80000/0x5000".

When rebuilding, remove all files without constraints from afs_rebuild.csv. Then put auto in indexes and offsets that doesn't have constraints. While rebuilding the AFS filename_resolver.csv will be removed but you can keep changes about filenames by adding entries with unpacked_filename+index (and packed_filename when there is a FD) into this file.

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
