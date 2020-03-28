68k checker by JOTD v1.0, released on 17/03/2014


usage: m68kchecker -i my_source.asm > log.txt

features:
 - tries to detect backwards branches with no memory changes in between
 (some false alarms, but handy!)
 - tries to detect writes to labels where there's SMC (heuristic too)
 - checks accesses to SR, VBR ...


Requirements:

M68kchecker needs IRA disassembled output (also works with d68k AFAIR), but can
also take executables directly (IRA binary is called if input is an amiga exe,
you must put an executable version of IRA for your OS in "ira" directory).

Download ira with source code at http://aminet.net/dev/asm/ira.lha

ira must be called like this when used outside the program:

ira -a -m68020 myamigaexe
=> creates "myamigaexe.asm" in the same directory

It also requires python 2.5 (other versions like 2.6 or 2.7 should work too)
