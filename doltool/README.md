# doltool.py
**Tests on -sr command and sections remapping has to be done.**

Python3 script for manipulating dol file format. This tool can stats with all informations from dol header and patch dol .text and .data using a list of write Action Replay code in an formated .ini file. MIT License.

## User manual
Translate a virtual address into a dol offset if this was originaly mapped from data or text. virtual_address has to be in hexadecimal: 80003100
```
doltool.py --virtual2image virtual_address
```

Translate a dol offset to a virtual address mapped from data or text. dol_offset has to be in hexadecimal: 2000
```
doltool.py --image2virtual dol_offset
```

Extract a section_index between 0 to 17 from the dol file **source.dol** with the name  _source.dol\_sectiontypeN_. sectiontype = data or text and N is the index from 0 to 17.
```
doltool.py --extract source.dol section_index [-o output_file]
```

Print stats about the dol file. This stats contains informations about full header information formated (with sections used or not), empty spaces informations splited .bss and entry point.
```
doltool.py --stats source.dol
```

Patch the dol data and text section using an action_replay.ini file containing write instructions (02/04 implemented yet). If the virtual address of the ARCode doesn't match existing mapped data or text sections it raise an Exception. To avoid this exception use the -sr argument to auto remap dol offsets and create a new data section reserved for the patching process.
```
doltool.py --patch-action-replay source.dol -ini action_replay_list.ini [-sr]
```

## Action Replay ini file format
All ARCodes present in the ini will be enabled without taking care of \[ActionReplay_Enabled\] section
Raise an Exception if lines are in invalid format:
* empty lines are removed
* lines beginning with $ are considered as comments and are removed
* lines beginning with \[ are considered as comments and are removed
* others lines have to be in format: "0AXXXXXX XXXXXXXX" with (A=2 or A=4) and X in \[0-9a-fA-F\]
