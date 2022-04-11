# gcmtool.py
Python3 script for unpack/pack/rebuild GCM/iso file format. This tool can rebuild FileStringTable (FST) of GCM and patch boot.bin with a new apploader.img, boot.dol, add/remove/edit folder and files of the game. MIT License.

## User manual
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
Japanese charset is not handled for now except if you have installed Japanese local.

The original GCM/iso and repack GCM/iso are different most of the time. This is because GCM DVD contains "empty spaces" with data unused (old datas or random datas I don't know). So this datas are useless and loss during unpack.

The sorting of files during FST rebuild is deferent from the original and this is full compatible with the GameCube dol API.

## Extracted file tree
root folder contains all files of the unpacked GCM/iso

sys folder contains GCM system files of the game:
* boot.bin
* bi2.bin
* apploader.img
* boot.dol
* fst.bin
