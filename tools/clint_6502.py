"""
clint.py - carry-flow lint for 6502->68k translated code

usage: python3 clint.py gravitar.68k

Within each block between labels, reports:
  C  <line>: a carry branch (bcc/bcs/bhi/bls) whose C was set by a
             carry producer (cmp, add, sub, addx, shifts, SET/CLR_XC_FLAGS...)
             then destroyed by an instruction whose 6502 original doesn't
             touch C (move, and, or, eor, tst, clr, addq, subq, GET_ADDRESS...)
  X  <line>: an addx/subx/abcd/sbcd/roxl/roxr (or SBC_IMM...) whose X was
             changed by addq/subq/shift since the last carry producer,
             or only set by a cmp (68k cmp doesn't set X)
Code between PUSH_SR and POP_SR is skipped (flags restored).
After a jsr, the carry is assumed live (the subroutine may return a
result in C), so a move/subq... before a bcc/bcs is reported too.
Limits: doesn't follow carries across labels or branches, so it can
miss cases (e.g. a carry returned by a subroutine); it never proves code correct.
"""
import re, sys
lines = [l for l in open(sys.argv[1]).read().split('\n')]
def strip(l):
    i = l.find('|')
    code = l if i < 0 else l[:i]
    cm = '' if i < 0 else l[i+1:]
    return code.strip(), cm.strip()
C_PROD = re.compile(r'^(cmp|sub|add|addx|subx|asl|asr|lsl|lsr|roxl|roxr|abcd|sbcd|neg|negx|cmpa|cmpi|subi|addi)(\.[bwl])?\b')
C_MAC = ('SET_XC_FLAGS','CLR_XC_FLAGS','INVERT_XC_FLAGS','SET_C_FROM_X','SET_X_FROM_C','SET_X_FROM_CLEARED_C','POP_SR')
C_KILL = re.compile(r'^(move|moveq|and|or|eor|andi|ori|eori|tst|clr|addq|subq|ext|not|mulu|muls|divu|divs|swap)(\.[bwl])?\b')
X_KILL = re.compile(r'^(addq|subq|add|sub|asl|asr|lsl|lsr|neg|addi|subi)(\.[bwl])?\b')
X_USE = re.compile(r'^(addx|subx|abcd|sbcd|roxl|roxr)(\.[bwl])?\b')
C_USE = re.compile(r'^j?b?(cc|cs|hi|ls)\b|^(bcc|bcs|bhi|bls|jcc|jcs|jhi|jls)\b')
state = None  # 'ok' after producer, ('killed', lineno, text) after kill
xstate = None
depth = 0
for n, raw in enumerate(lines, 1):
    if 'LOG_REGS' in raw:
        continue
    code, cm = strip(raw)
    if not code or code.startswith('*'):
        continue
    if re.match(r'^[A-Za-z_.0-9]+:', code):
        state = None; xstate = None; depth = 0
        code = code.split(':',1)[1].strip()
        if not code: continue
    op = code.split()[0]
    if op.startswith('OP_') and len(code.split()) > 1:
        # OP_R_ON_ZP_ADDRESS move,var,d0 -> analyse as "move"
        inner = code.split(None,1)[1].split(',')[0].strip()
        code = inner + ' ' + code.split(None,1)[1].split(',',1)[1]
        op = inner
    if op == 'PUSH_SR':
        depth += 1; continue
    if op == 'POP_SR':
        depth = max(0, depth-1)
        if depth == 0: continue
    if depth: continue
    if re.match(r'^(jbsr|jsr|bsr|rts|jra|jmp|bra|rte)\b', op):
        if op.startswith(('jbsr','jsr','bsr')):
            # a subroutine may return its result in C (6502 convention):
            # treat the carry as live after the call
            state='ok'; xstate='ok'
        continue
    if op in ('SBC_IMM','SBCD_IMM','ADC_IMM','ADCD_IMM'):
        if isinstance(xstate, tuple):
            print(f"X  {n}: {code:40s} | {cm[:40]}   <- X killed at {xstate[1]}: {xstate[2]}")
        state = 'ok'; xstate = 'ok'
        continue
    if X_USE.match(code) and isinstance(xstate, tuple):
        print(f"X  {n}: {code:40s} | {cm[:40]}   <- X killed at {xstate[1]}: {xstate[2]}")
    if (op.startswith('b') or op.startswith('j')) and op.lstrip('j').lstrip('b') in ('cc','cs','hi','ls') or op in ('bcc','bcs','jcc','jcs','bhi','bls','jhi','jls'):
        if isinstance(state, tuple):
            print(f"C  {n}: {code:40s} | {cm[:40]}   <- C killed at {state[1]}: {state[2]}")
        continue
    if re.match(r'^cmp[ia]?(\.[bwl])?$', op):
        # 68k cmp sets C but not X: a following addx/subx/SBC_IMM would use a stale X
        state = 'ok'; xstate = ('killed', n, code + '   (cmp does not set X)')
        continue
    if op in C_MAC or C_PROD.match(code):
        state = 'ok'
        if X_USE.match(code) or op in C_MAC or re.match(r'^(add|sub|asl|asr|lsl|lsr|neg|roxl|roxr|addx|subx|abcd|sbcd|addi|subi)\b',op): xstate='ok'
        continue
    if op == 'GET_ADDRESS' or C_KILL.match(code):
        if 'movem' in op: continue
        # 6502 origin preserves C for lda/ldx/ldy/sta/stx/sty/inc/dec/and/ora/eor/tax/tay/txa/tya/[...]
        if state == 'ok':
            state = ('killed', n, code)
        if X_KILL.match(code) and xstate == 'ok':
            xstate = ('killed', n, code)
