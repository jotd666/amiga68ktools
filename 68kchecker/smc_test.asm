start:
	move.w	d0,LAB_1234+2
	nop
	clr	d0
	move.w	d0,LAB_1235+4
LAB_1234:
	move.w	#$0012,d1
	rts
LAB_1235:
	move.w	#$0012,$1230
	rts
	nop
	nop
	nop
	
LAB_0D0A:
	DBF	D2,LAB_0D0A		;12A9C: 51CAFFFE
	RTS				;12AA0: 4E75
	