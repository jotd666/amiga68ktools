#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
iso2cdtv
(c) MML, 2012
"""

# Convert an ISO9660 file to an bootable CDTV ISO
#
# The ISO file is built using mkisofs (cdrtools 3.0) with those parameters:
# mkisofs -quiet -V <cd_name> -copyright <your_copyright> -publisher <publisher_name> 
# -o <name.raw> -relaxed-filenames -d -input-charset ASCII -output-charset ASCII 
# -iso-level 3 -A "" -sysid CDTV <folder_name>

import sys
import glob             # glob() expande los patrones de los ficheros en windows
import os               # path.basename(), path.exists()
from optparse import make_option, OptionParser

# CDTV Application Data Field
CDTV_AppDat = b'\x00\x54\x4D\x00\x14\x00\x00\x56\x88'

# 00 01 00 00 54 4d 00 14 00 00 56 88
# xx xx xx xx XX XX XX XX xx xx xx xx XX XX XX XX
# 00 00 00 00
# 8373 8b73 dos copias
# xx xx xx xx * 2048 => Localización del fichero CDTV.TM (Big Endian)
#                  RTS            c   d   t   v       3   5   .   2
CDTV_TM = b'\x4E\x75\x00\x00\x63\x64\x74\x76\x20\x33\x35\x2E\x32\x20'

# Procesa la línea de comandos    
def procesar_linea_comandos(linea_de_comandos):
    """
    Devuelve una tupla de dos elementos: (opciones, lista_de_ficheros).
    `linea_de_comandos` es una lista de argumentos, o `None` para ``sys.argv[1:]``.
    """
    if linea_de_comandos is None:
        linea_de_comandos = sys.argv[1:]

    version_programa = "%prog v0.1"
    uso_programa = "usage: %prog [options] file1.raw file2.raw ... fileX.raw"
    descripcion_programa = "%prog transform RAW ISO images to CDTV bootable ISOs."

    # definimos las opciones que soportaremos desde la lnea de comandos
    lista_de_opciones = []
        
    parser = OptionParser(usage=uso_programa, description=descripcion_programa,
        version=version_programa, option_list=lista_de_opciones)
    
    # obtenemos las opciones y la lista de ficheros suministradas al programa
    (opciones, lista_ficheros_tmp) = parser.parse_args(linea_de_comandos)

    # comprobamos el número de argumentos y verificamos los valores
    if (not lista_ficheros_tmp):
        parser.error("No files to process.")
    else:
        lista_ficheros = []
        for i in lista_ficheros_tmp:
            lista_ficheros = lista_ficheros + glob.glob(i)

    return opciones, lista_ficheros

def main(linea_de_comandos=None):
    """
    Main function
    """
    # Get commandline arguments
    opciones, lista_ficheros = procesar_linea_comandos(linea_de_comandos)

    for nombre_fichero in lista_ficheros:
        # Process files
        if not(os.path.exists(nombre_fichero)):
            print ("The file %s doesn't exist.", nombre_fichero)
            continue

        # Open file
        iso_tmp = b""
        print ("Loading file: " + nombre_fichero)
        with open(nombre_fichero,"rb") as fichero:
            iso_tmp = fichero.read()

        # Check l_path_table and m_path_table
        if (iso_tmp[0x808C] != 0x13) and (iso_tmp[0x8097] != 0x15):
            print ("Invalid ISO image")
        else:
            # Search CDTV.TM in the disk
            indice = iso_tmp.find(CDTV_TM) // 0x800
            if (indice != -1):
                # Convert index to big endian
                indice = bytes((indice // 16777216, 
                                (indice % 16777216) // 65536,
                                ((indice % 16777216) % 65536) // 256,
                                ((indice % 16777216) % 65536) % 256))
                CDTV_AppDat_tmp =  iso_tmp[0x8370: 0x8373] + CDTV_AppDat + indice * 4

                # Insert the two copies of Application Data Field
                iso_tmp = iso_tmp [0: 0x8370] + CDTV_AppDat_tmp + \
                            iso_tmp [0x8370 + len(CDTV_AppDat_tmp): 0x8B70] + \
                            CDTV_AppDat_tmp + iso_tmp [0x8B70 + len(CDTV_AppDat_tmp):]

                # Save the ISO file
                print ("Saving file: " + nombre_fichero.lower().replace(".raw",".iso"))
                with open(nombre_fichero.lower().replace(".raw",".iso"),"wb") as fichero:
                    fichero.write(iso_tmp)
            else:
                print("CDTV.TM doesn't exist in the ISO image.")

    return 0    # EXIT_SUCCESS

if __name__ == "__main__":
    estado = main()
    sys.exit(estado)
