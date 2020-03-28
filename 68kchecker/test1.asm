start:
	MOVE.L	#2,D0
	RESET
	RTS
	;; comment
	dc.b	$0
	MOVEC	D0,VBR
	MOVE	CACR,D0
	MOVE	SR,D0
;;; 
	MOVE	D0,SR
	
	