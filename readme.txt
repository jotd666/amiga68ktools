a collection of python tools and libraries to handle amiga objects, with a focus
on reverse engineering / whdload patching

Some of those tools need the IRA disassembler.

* tools (the more interesting part):

tools/asmdiff.py: compares 2 IRA-resourced files for differences, ignoring labels
tools/find_slave_relocs.py: helps finding omitted relocations in whdload slaves
tools/mod_renamer.py: just renames mod.xxx to xxx.mod
tools/rtb2reloc.py: decodes relocation tables (.RTB) to offsets
tools/uaeunp_wrapper.py: just calls uaeunp on several adf files
tools.wmake.py
tools/make_cdtv_iso.py: not my work, but interesting: creates ISO files for CDTV
tools/whdload_slave.py: can parse a whdload slave and extract info from it
tools/cheapres.py: cheap resourcer from IRA disassembled source. Names system calls (using LVOs.i)
                   and also names custom registers offsets
tools/wdate.py: same as amiga wdate (whdload), but in python for cross compilation
tools/whdslave_resourcer.py: disassembles whdload slave (ira) and tries to find patchlists & resload calls
tools/scan_slaves.py: scans a directory tree for whdload slaves/games and creates a sheet with characteristics (memory, ecs/aga...)
tools/find_memory_gaps.py: scans a winuae memory dump for "empty" areas (useful to insert savebuffers/cdbuffers)
tools/whd_to_patchlist.py: converts patch instructions to patchlists. Support for JST macros too

* 68kchecker: program to find possible self-modifying code or cpu dependent code or other from IRA source

* Personal tools: you probably don't care much as those are my custom scripts

* this lib directory needs to be added to PYTHONPATH for some tools to work

lib/bitplanelib.py: reads & writes bitplanes, allows to convert PNGs to bitplanes and reverse, with palette order management!!
lib/ira_asm_tools.py: a bit late, but centralized functions to handle IRA disassemblies
lib/whdload_slave.py: object to parse whdload binary slaves
lib/asm_parsing.py: (lame) assembly parser for IRA

