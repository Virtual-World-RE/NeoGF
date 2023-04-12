# NeoGF
NeoGF is a library of tools for GameCube and Gotcha Force.

> This project is still under "heavy" development. It not yet 100% ready to use.
> 
> Do not hesitate to contribute.

If you want more infos about the game, go read our [Gotcha Force Wiki](http://re.wiki.virtualworld.fr/index.php/Gotcha_Force).

#### gcmtool
Python3 script for unpack/pack/rebuild GCM/iso file format. This tool can rebuild FileStringTable (FST) of GCM and patch boot.bin with a new apploader.img, boot.dol, add/remove/edit folder and files of the game. MIT License.

#### afstool
Python3 script for unpack/pack/rebuild AFS file format. Rebuild of Table of content (TOC) and Filename directory (FD) is possible with full controll of every parameters. MIT License.

#### doltool
Python3 script for manipuling dol file format. This tool can stats with all informations from dol header and patch dol .text and .data using a list of write Action Replay code in an formated .ini file. MIT License.

#### pzztool
Python3 script for unpack/repack unpzz/pzz and uncompress/compress of PZZ archive. Handle also ARZ files decompression. MIT License.

#### mdttool
Python3 script for unpack/pack MDT file format. Allow to edit texts files extracted. MIT License.

#### mottool
Python3 script for unpack/pack MOT file format. MIT License.

#### data
CSV and datas for Gotcha Force game.

#### doc 
Documentation about reverse engineering Gotcha Force.
