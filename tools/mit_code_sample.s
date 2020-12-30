|	of these registers, it should modify the saved copy and let
|	the handler exit code restore the value.
|
|----------------------------------------------------------------------
|
|	Local Variables on the stack
|
	.set		LOCAL_SIZE,192	| bytes needed for local variables
	.set		LV,-LOCAL_SIZE	| convenient base value
|
	.set		USER_DA,LV+0	| save space for D0-D1,A0-A1
	.set		USER_D0,LV+0	| saved user D0
	.set		USER_D1,LV+4	| saved user D1
	.set		USER_A0,LV+8	| saved user A0
	.set		USER_A1,LV+12	| saved user A1
	.set		USER_FP0,LV+16	| saved user FP0
	.set		USER_FP1,LV+28	| saved user FP1
	.set		USER_FP2,LV+40	| saved user FP2
	.set		USER_FP3,LV+52	| saved user FP3
	.set		USER_FPCR,LV+64	| saved user FPCR
	.set		FPCR_ENABLE,USER_FPCR+2	| FPCR exception enable
	.set		FPCR_MODE,USER_FPCR+3	| FPCR rounding mode control

//		Copyright (C) Motorola, Inc. 1990
//			All Rights Reserved
//
//	THIS IS UNPUBLISHED PROPRIETARY SOURCE CODE OF MOTOROLA
//	The copyright notice above does not evidence any
//	actual or intended publication of such source code.

GEN_EXCEPT:    //idnt    2,1 | Motorola 040 Floating Point Software Package

	|section 8

	.include "fpsp.defs"

	|xref	real_trace
	|xref	fpsp_done
	|xref	fpsp_fmt_error

exc_tbl:
	.long	bsun_exc
	.long	commonE1
	.long	commonE1
	.long	ovfl_unfl
	.long	ovfl_unfl
	.long	commonE1
	.long	commonE3
	.long	commonE3
	.long	no_match

	.global	gen_except
gen_except:
	cmpib	#IDLE_SIZE-4,1(%a7)	//test for idle frame
	beq	do_check		//go handle idle frame
	cmpib	#UNIMP_40_SIZE-4,1(%a7)	//test for orig unimp frame
	beqs	unimp_x			//go handle unimp frame
	cmpib	#UNIMP_41_SIZE-4,1(%a7)	//test for rev unimp frame
	beqs	unimp_x			//go handle unimp frame
	cmpib	#BUSY_SIZE-4,1(%a7)	//if size <> $60, fmt error
	bnel	fpsp_fmt_error
	leal	BUSY_SIZE+LOCAL_SIZE(%a7),%a1 //init a1 so fpsp.h
//					;equates will work
// Fix up the new busy frame with entries from the unimp frame
//
	movel	ETEMP_EX(%a6),ETEMP_EX(%a1) //copy etemp from unimp
	movel	ETEMP_HI(%a6),ETEMP_HI(%a1) //frame to busy frame
	movel	ETEMP_LO(%a6),ETEMP_LO(%a1)
	movel	CMDREG1B(%a6),CMDREG1B(%a1) //set inst in frame to unimp
	movel	CMDREG1B(%a6),%d0		//fix cmd1b to make it
	andl	#0x03c30000,%d0		//work for cmd3b
	bfextu	CMDREG1B(%a6){#13:#1},%d1	//extract bit 2
	lsll	#5,%d1
	swap	%d1
	orl	%d1,%d0			//put it in the right place
	bfextu	CMDREG1B(%a6){#10:#3},%d1	//extract bit 3,4,5
	lsll	#2,%d1
	swap	%d1
	orl	%d1,%d0			//put them in the right place
	movel	%d0,CMDREG3B(%a1)		//in the busy frame
//
// Or in the FPSR from the emulation with the USER_FPSR on the stack.
//
	fmovel	%FPSR,%d0
	orl	%d0,USER_FPSR(%a6)
	movel	USER_FPSR(%a6),FPSR_SHADOW(%a1) //set exc bits
	orl	#sx_mask,E_BYTE(%a1)
	bra	do_clean

//
	bclrb	#sign_bit,LOCAL_EX(%a0)	//get rid of fake sign
	bfclr	LOCAL_SGN(%a0){#0:#8}	//convert back to IEEE ext format
	beqs	den_com
	bsetb	#sign_bit,LOCAL_EX(%a0)
den_com:
	moveb	#0xfe,CU_SAVEPC(%a2)	//set continue frame
	clrw	NMNEXC(%a2)		//clear NMNEXC
	bclrb	#E1,E_BYTE(%a2)
//	fmove.l	%FPSR,FPSR_SHADOW(%a2)
//	bset.b	#SFLAG,E_BYTE(%a2)
//	bset.b	#XFLAG,T_BYTE(%a2)
end_avun:
	frestore (%a7)+
	unlk	%a2
	rts
idle_end:
	addl	#4,%a7
	unlk	%a2
	rts