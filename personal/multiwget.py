sfiles='''bindec.s
binstr.s
bugfix.s
decbin.s
do_func.s
fpsp.defs
gen_except.s
get_op.s
kernel_ex.s
Makefile.in
README
res_func.s
round.s
rtems_fpsp.c
rtems_skel.s
sacos.s
sasin.s
satan.s
satanh.s
scale.s
scosh.s
setox.s
sgetem.s
sint.s
slog2.s
slogn.s
smovecr.s
srem_mod.s
ssin.s
ssinh.s
stan.s
stanh.s
sto_res.s
stwotox.s
tbldo.s
util.s
x_bsun.s
x_fline.s
x_operr.s
x_ovfl.s
x_snan.s
x_store.s
x_unfl.s
x_unimp.s
x_unsupp.s'''.splitlines()

import wget

url = "https://devel.rtems.org/export/f9b93da8b47ff7ea4d6573b75b6077f6efb8dbc6/rtems/c/src/lib/libcpu/m68k/m68040/fpsp/"
for sfile in sfiles:
    f = wget.download(url+sfile)
    print(f)