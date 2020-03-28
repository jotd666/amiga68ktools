#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      dartypc
#
# Created:     16/02/2020
# Copyright:   (c) dartypc 2020
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import re,os

dma_re = re.compile("DMA pointer ([\dA-F]+) \((\w+)\) set to invalid value ([\dA-F]+) PC=([\dA-F]+)",flags=re.I)
# DMA DAT 008c (COPINS), PT 0080 (COP1LCH) accessed invalid memory 47f6da36. Init: 47f6da36, PC/COP=47f538d0
cop_re = re.compile("DMA .* \(\w+\), PT ([\dA-F]+) \((\w+)\) accessed invalid memory ([\dA-F]+). Init: ([\dA-F]+), PC/COP=([\dA-F]+)",flags=re.I)
messages_marker = set()
messages = []

def message(m):
    if m not in messages_marker:
        messages.append(m+"\n")
        messages_marker.add(m)

def main():
    logfile = r"C:\Users\Public\Documents\Amiga Files\WinUAE\winuaelog.txt"
    expmem = 0

    with open(logfile) as f:
        for line in f:
            m = dma_re.search(line)
            if m:

                custom_addr,custom_name,write_address,pc = m.groups()
                write_address = int(write_address,16)
                if custom_name == "AUD0LCH" and expmem == 0:
                    continue
                elif custom_name == "AUD0LCL" and expmem == 0:
                    expmem = write_address
                    message("expmem = ${:08x}".format(expmem))
                    continue
                pc = int(pc,16)
                if expmem and pc > expmem:
                    pc -= expmem
                    pctype = "EXPMEM+"
                else:
                    pctype = "PC="
                if write_address > expmem:
                    write_address -= expmem
                    adtype = "EXPMEM+"
                else:
                    adtype = "PC="
                message("{} ({}) out of bounds val={}${:08x} at {}${:08x}".format(custom_addr,custom_name,adtype,write_address,pctype,pc))
            else:
                m = cop_re.search(line)
                if m:
                    custom_addr,custom_name,write_address,init,pc = m.groups()
                    pc = int(pc,16)
                    if expmem and pc > expmem:
                        pc -= expmem
                        pctype = "EXPMEM+"
                    else:
                        pctype = "PC="
                    write_address = int(write_address,16)
                    if expmem and write_address > expmem:
                        write_address -= expmem
                        adtype = "EXPMEM+"
                    else:
                        adtype = "PC="
                    message("{} ({}) copper out of bounds val={}${:08x} at {}${:08x}".format(custom_addr,custom_name,adtype,write_address,pctype,pc))

    outfile = os.path.join(os.getenv("TEMP"),"out.txt")
    with open(outfile,"w") as f:
        f.writelines(messages)
    # trunc log
    #with open(logfile,"w") as f:
    #    pass
    os.startfile(outfile)
if __name__ == '__main__':
    main()
