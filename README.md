# NeoGF
NeoGF is a library of tools for Gotcha Force.

Pour plus d'info sur le jeu, rendez vous sur le [Wiki](http://re.wiki.virtualworld.fr/index.php/Gotcha_Force).

## pzztool.py
Python3 script for unpack/repack and uncompress/compress of PZZ archive.

### User manual

Every file extracted has a name using the format :

AAAB_CD.E
- AAA is the 3 digits index of the file in the PZZ starting at 000.
- B describe the compression state of the file when packed in the PZZ. If compressed it's **C** and if not it's **U**.
- C is the name of the PZZ.
- D describe the actual compression state of the file. It's **\_compressed** if the file is compressed and nothing if the file is uncompressed.
- E is the extension of the file. By default it is **.dat**

For example file 012C_cmn_data.dat describe the 13th file off the pzz initialy compressed in a pzz named "cmn_data.pzz" and that has been uncompressed with the default format "dat". The names of unpacked files and the presence of empty unpacked files are important to keep informations relative to the initial pzz and ensure a correct pack.

```
pzztool.py -u source.pzz optional_dest_folder
```
Unpack **source.pzz** in the default new folder _source_.

If optional_dest_folder is specified we unpack in _optional_dest_folder_.
```
pzztool.py -p source_folder optional_dest.pzz
```
Pack **source_folder** in the default new pzz file _source_folder.pzz_.

If optional_dest.pzz is specified we pack in _optional_dest.pzz_.
```
pzztool.py -bu source_folder optional_dest_folder
```
Unpack every pzz files present in _source_folder_ using the same directory. For each pzz a folder is created using the name of the pzz.

If optional_dest_folder is specified we unpack all files in _optional_dest_folder_ instead of source_folder.
```
pzztool.py -bp source_folder optional_dest_folder
```
Pack every folder present in _source_folder_ using the same directory. For each folder a pzz file a folder is created using the name of the pzz.

If optional_dest_folder is specified we pack all folders in _optional_dest_folder_ instead of source_folder.
