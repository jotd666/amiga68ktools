import struct

text="""
@atan:
	DC.W	$f227			;4f312
	BMI.S	LAB_2558		;4f314: 6b80
	DC.W	$f200			;4f316
	BCLR	D1,D0			;4f318: 0380
	DC.W	$f200			;4f31a
	DC.W	$1c0a			;4f31c
	DC.W	$f21f			;4f31e
	CHK.W	D0,D5			;4f320: 4b80
	RTS				;4f322: 4e75
"""

text="""
	DC.W	$f200			;2cfc4
	ADDQ.B	#6,(44,A2,A7.W*2)	;2cfc6: 5c32f22c
	MOVEQ	#0,D2			;2cfca: 7400
	MOVE.B	(LAB_1561,PC),(29696,A3) ;2cfcc: 177af22c7400
	MOVE.B	D2,(44,A3,A7.W*2)	;2cfd2: 1782f22c
	NEGX.B	D0			;2cfd6: 4000
	DC.W	$f3fe			;2cfd8
	DC.W	$f22c			;2cfda
	NEG.L	D0			;2cfdc: 4480
	AND.B	D5,(A2)			;2cfde: cb12
	DC.W	$f200			;2cfe0
	BTST	D2,D0			;2cfe2: 0500
	DC.W	$f200			;2cfe4
	DC.W	$0823			;2cfe6
	DC.W	$f22c			;2cfe8
	MOVEQ	#0,D2			;2cfea: 7400
	MOVE.B	EXT_0069.W,(7040,A5)	;2cfec: 1b7842ac1b80
	CLR.L	(7044,A4)		;2cff2: 42ac1b84
	CLR.L	(7048,A4)		;2cff6: 42ac1b88
	CLR.L	(7052,A4)		;2cffa: 42ac1b8c
	MOVE.W	(4620,A4),D0		;2cffe: 302c120c
	EXT.L	D0			;2d002: 48c0
	BSR.W	LAB_154D		;2d004: 6100d848
	DC.W	$f22c			;2d008
	ADDQ.B	#2,-(A3)		;2d00a: 5423
	MOVE.B	EXT_0055.W,(4622,A5)	;2d00c: 1b78302c120e
	EXT.L	D0			;2d012: 48c0
	DC.W	$f22f			;2d014
	MOVEQ	#0,D2			;2d016: 7400
	DC.W	$0010			;2d018
	BSR.W	LAB_154D		;2d01a: 6100d832
	DC.W	$f22c			;2d01e
	ADDQ.B	#2,-(A3)		;2d020: 5423
	MOVE.B	D0,(47,A5,A7.W*2)	;2d022: 1b80f22f
	ADDQ.L	#2,D0			;2d026: 5480
	DC.W	$0010			;2d028
	DC.W	$f200			;2d02a
	ORI.L	#$302c1210,-(A2)	;2d02c: 00a2302c1210
	EXT.L	D0			;2d032: 48c0
	DC.W	$f22f			;2d034
	MOVEQ	#-128,D2		;2d036: 7480
	DC.W	$0010			;2d038
	BSR.W	LAB_154D		;2d03a: 6100d812
	DC.W	$f22c			;2d03e
	ADDQ.B	#2,-(A3)		;2d040: 5423
	DC.W	$1b88			;2d042
	DC.W	$f22f			;2d044
	ADDQ.L	#2,D0			;2d046: 5480
	DC.W	$0010			;2d048
	DC.W	$f200			;2d04a
	ORI.L	#$f22c7480,-(A2)	;2d04c: 00a2f22c7480
	MOVE.B	(12332,A0),(18,A5,D1.W*2) ;2d052: 1ba8302c1212
	EXT.L	D0			;2d058: 48c0
	BSR.W	LAB_154D		;2d05a: 6100d7f2
	DC.W	$f22c			;2d05e
	ADDQ.B	#2,-(A3)		;2d060: 5423
	MOVE.B	EXT_0055.W,(4628,A5)	;2d062: 1b78302c1214
	EXT.L	D0			;2d068: 48c0
	DC.W	$f22f			;2d06a
	MOVEQ	#0,D2			;2d06c: 7400
	DC.W	$0010			;2d06e
	BSR.W	LAB_154D		;2d070: 6100d7dc
	DC.W	$f22c			;2d074
	ADDQ.B	#2,-(A3)		;2d076: 5423
	MOVE.B	D0,(47,A5,A7.W*2)	;2d078: 1b80f22f
	ADDQ.L	#2,D0			;2d07c: 5480
	DC.W	$0010			;2d07e
	DC.W	$f200			;2d080
	ORI.L	#$302c1216,-(A2)	;2d082: 00a2302c1216
	EXT.L	D0			;2d088: 48c0
	DC.W	$f22f			;2d08a
	MOVEQ	#-128,D2		;2d08c: 7480
	DC.W	$0010			;2d08e
	BSR.W	LAB_154D		;2d090: 6100d7bc
	DC.W	$f22c			;2d094
	ADDQ.B	#2,-(A3)		;2d096: 5423
	DC.W	$1b88			;2d098
	DC.W	$f22f			;2d09a
	ADDQ.L	#2,D0			;2d09c: 5480
	DC.W	$0010			;2d09e
	DC.W	$f200			;2d0a0
	ORI.L	#$f22c7480,-(A2)	;2d0a2: 00a2f22c7480
	MOVE.B	(44,A0,D3.W),(24,A5,D1.W*2) ;2d0a8: 1bb0302c1218
	EXT.L	D0			;2d0ae: 48c0
	BSR.W	LAB_154D		;2d0b0: 6100d79c
	DC.W	$f22c			;2d0b4
	ADDQ.B	#2,-(A3)		;2d0b6: 5423
	MOVE.B	EXT_0055.W,(4634,A5)	;2d0b8: 1b78302c121a
	EXT.L	D0			;2d0be: 48c0
	DC.W	$f22f			;2d0c0
	MOVEQ	#0,D2			;2d0c2: 7400
	DC.W	$0010			;2d0c4
	BSR.W	LAB_154D		;2d0c6: 6100d786
	DC.W	$f22c			;2d0ca
	ADDQ.B	#2,-(A3)		;2d0cc: 5423
	MOVE.B	D0,(47,A5,A7.W*2)	;2d0ce: 1b80f22f
	ADDQ.L	#2,D0			;2d0d2: 5480
	DC.W	$0010			;2d0d4
	DC.W	$f200			;2d0d6
	ORI.L	#$302c121c,-(A2)	;2d0d8: 00a2302c121c
	EXT.L	D0			;2d0de: 48c0
	DC.W	$f22f			;2d0e0
	MOVEQ	#-128,D2		;2d0e2: 7480
	DC.W	$0010			;2d0e4
	BSR.W	LAB_154D		;2d0e6: 6100d766
	DC.W	$f22c			;2d0ea
	ADDQ.B	#2,-(A3)		;2d0ec: 5423
	DC.W	$1b88			;2d0ee
	DC.W	$f22f			;2d0f0
LAB_1586:
	ADDQ.L	#2,D0			;2d0f2: 5480
	DC.W	$0010			;2d0f4
	DC.W	$f200			;2d0f6
	ORI.L	#$f22c7480,-(A2)	;2d0f8: 00a2f22c7480
	DC.W	$1bb8			;2d0fe
    """
sizedict = {"W":2,"B":1,"L":4}
fmt_dict = {1 : "B", 2 :"H", 4 : "I", 8 : "Q", 6 : "Q"}
def decode_dc(line):
    toks = line.split()
    if len(toks)>2 and toks[0][:-1]=="DC.":
        size = toks[0][-1]
        return int(toks[1][1:],16),sizedict[size]

lines = text.splitlines()
lst = []
# get opcode
for line in lines:
    dc = decode_dc(line)
    if dc is None:
        if ";" in line and ":" in line:
            val = line.rsplit(":",1)[-1].strip()
            dc = int(val,16),len(val)//2

    if dc is not None:
        size = dc[1]
        fmt = ">{}".format(fmt_dict[size])
        pck = struct.pack(fmt,dc[0])
        if size==6:
            # truncate
            pck = pck[2:]
        lst.append(pck)
print(lst)
CODE = b"".join(lst)
print(CODE)
#CODE = b"\x55\x48\x8b\x05\xb8\x13\x00\x00"

from capstone import *
md = Cs(CS_ARCH_M68K,CS_MODE_M68K_060)
for i in md.disasm(CODE, 0x1000):
    print("0x%x:\t%s\t%s" %(i.address, i.mnemonic, i.op_str))
