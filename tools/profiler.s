; < A0: buffer start
; < D0: buffer size
; < A1: where to read control & write start & size (example $100.W)
init_fixed_address
	movem.l	d0/a0-a2,-(a7)
	lea	profiler_control(pc),a2
	move.l	a1,(a2)
	clr.l	(a1)+
	move.l	a0,(a1)+
	move.l	d0,(a1)
	lea	buffer_start(pc),a2
	move.l	a0,(a2)
	lea	buffer_pointer(pc),a2
	move.l	a0,(a2)
	lea	buffer_end(pc),a2
	add.l	a0,d0
	move.l	d0,(a2)
	lea	buffer_size(pc),a2
	clr.l	(a2)
	movem.l	(a7)+,d0/a0-a2
	rts
	
; < D0: buffer size
; < A1: where to read control & write start & size (example $100.W)
init_allocated_address
	movem.l	d1/a0/a6,-(a7)
	move.l	4,A6
	move.l	#MEMF_PUBLIC|MEMF_CLEAR,d1
	movem.l	d0/a1,-(a7)
	jsr		_LVOAllocMem(a6)
	move.l	d0,a0
	movem.l	(a7)+,d0/a1
	bsr		init_fixed_address
	movem.l	(a7)+,d1/a0/a6
	rts
	
; if program to profile is using OS calls, it's better to
; hook vbl directly on VBLANK
	
install_profiler_vbl_hook:
	move.l	a0,-(a7)
	lea		old_vbl(pc),a0
	move.l	$6C,(a0)
	lea		profiler_vbl_interrupt(pc),a0
	move.l	a0,$6C
	move.l	(a7)+,a0
	rts
	
profiler_vbl_interrupt
	movem.l	d0/a0,-(a7)
	move.l	10(a7),d0	; PC where interrupt occurred
	move.l	USP,a0
	bsr		profiler_vbl_hook
	movem.l	(a7)+,d0/a0
	move.l	old_vbl(pc),-(a7)
	rts
	
; < D0: current PC to log
; < A0: program stack
; call each vbl/copper interrupt
; for instance (can be a CIA fine timer interrupt too)

profiler_vbl_hook:
	movem.l	a0/a1/d1,-(a7)
	move.l	a0,d1		; SP to D1
	move.l	profiler_control(pc),a0
	tst.l	(a0)
	beq.b	.out
	
	lea		buffer_pointer(pc),a1
	move.l	(a1),a0
	cmp.l	buffer_end(pc),a0
	bcc.b	.out
	; log PC and stack (relative)
	move.l	d0,(a0)+
	move.l	d1,(a0)+
	move.l	a0,(a1)
	move.l	profiler_control(pc),a1
	sub.l	(4,a1),a0
	move.l	a0,(8,a1)	; update size
.out	
	movem.l	(a7)+,a0/a1/d1
	rts
	
profiler_control
	dc.l	0
buffer_start
	dc.l	0
buffer_pointer
	dc.l	0
buffer_end
	dc.l	0
buffer_size
	dc.l	0
old_vbl
	dc.l	0
