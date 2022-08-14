# gcmtool.py
Python3 script for unpack/pack/rebuild GCM/iso file format. This tool can rebuild FileStringTable (FST) of GCM and patch boot.bin with a new apploader.img, boot.dol, add/remove/edit folder and files of the game. MIT License.

## User manual
Unpack GCM/iso file **source_gcm.iso** in the default new folder _game_code-DVD_number_. If optional_dest_folder is specified we unpack in _optional_dest_folder_.
```
gcmtool.py --unpack source_gcm.iso optional_dest_folder
```
Pack **source_folder** in the default new GCM/iso file _source_folder.iso_. If optional_dest_file.iso is specified we pack in _optional_dest_file.iso_. If one of the files or system files contains length change we have to use --rebuild-fst command before packing. If the dol is duplicated in the FST use --disable-ignore to allow shared dol space.  If conf is enabled it will have priority on system values.
```
gcmtool.py --pack source_folder optional_dest_file.iso
```
Rebuild the FST file system of an unpacked GCM/iso and patch boot.bin for a new apploader, dol, and add/remove/edit of folders and files. If conf is enabled it will have priority on system values.
```
gcmtool.py --rebuild-fst source_folder
```
Print stats about the GCM/iso file or the unpacked GCM/iso folder. This stats contains informations about full memory mapping sorted by offset (files and system files), get empty spaces informations using optional align -a (default=4) and all conf values.
```
gcmtool.py --stats path -a 4 
```
Unpack and rebuild the FST of the unpacked folder.
```
gcmtool.py -ur source_gcm.iso optional_dest_folder
```
Rebuild the FST of the unpacked folder and pack.
```
gcmtool.py -rp source_folder optional_dest_file.iso
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

## sys/sytem.conf
The conf file system.conf allow to force somes values and patch sys/files and also new generated iso. The conf file is parsed and applied with --pack and --rebuild-fst.
### [Default]
* boot.bin_section = disabled / enabled # If enabled then boot.bin section will be applied.
* bi2.bin_section = disabled / enabled # If enabled then bi2.bin section will be applied.
* apploader.img_section = disabled / enabled # If enabled then apploader.img section will be applied.

### [boot.bin]
* GameCode = GG4P # 4 bytes ascii value - A-Za-z0-9
* MakerCode = 08 # 2 bytes ascii value - A-Za-z0-9
* DiskNumber = 0 # Disk number information for multiple disks. The number starts from 0. 0-98
* GameVersion = 0 # The version number of the video game. 0-99
* AudioStreaming = 1 # The flag for the streaming mode. 1 for streaming mode, otherwise 0.
* StreamBufferSize = 0 # Number of Streaming buffers. 0-15
* DVDMagic = 0xc2339f3d
* GameName = GotchaForceEur # The character string of the video game title (Kanji characters are available.). 64 bytes max.
* DolOffset = auto # Hex value: 0xabcdef or auto: dol offset on the DVD.
* FstOffset = auto # Hex value: 0xabcdef or auto: fst offset on the DVD
* FstLen = auto # Hex value: 0xabcdef or auto: fst length
* FstMaxLen = auto # Hex value: 0xabcdef or auto: the size of the area reserved for FST. Used when there is multiple FST to load (multiple DVD).
* UserPosition = auto # Hex value: 0xabcdef or auto: start of files stored in the gcm.
* UserLength = auto # Hex value: 0xabcdef or auto: length of files stored in the gcm.

### [bi2.bin]
* DebugMonitorSize = 0x0 # Hex value: 0xabcdef aligned to 32 bytes.
* SimulatedMemorySize = 0x1800000 # Hex value: 0xabcdef aligned to 32 bytes.
* ArgumentOffset = 0x0 # Hex value: 0xabcdef
* DebugFlag = 0 # Numeric value: 123. Set this to 0 when not using the any debugger on GDEV, set to 3 when using the CodeWarrior debugger on EV.
* TrackLocation = 0x0 # Hex value: 0xabcdef
* TrackSize = 0x0 # Hex value: 0xabcdef
* CountryCode = 2 # Numeric value: 123 - Japan=0, USA=1, PAL=2, SouthKorea=4
* TotalDisk = 1 # Numeric value: 1-99
* LongFileNameSupport = 1 # Numeric value. Set to 1 for long file name support; set to 0 to restrict file to 8.3 format.
* DolLimit = 0x0 # Hex value: 0xabcdef

### [apploader.img]
* Version = 2003/04/17
* EntryPoint = 0x81200258 # Hex value: 0xabcdef
* Size = 0x1954 # Hex value: 0xabcdef
* TrailerSize = 0x1b8b0 # Hex value: 0xabcdef
