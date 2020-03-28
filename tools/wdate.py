import sys,time

month=["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
lt=time.localtime()

t1 = time.strftime("(%d-{}-%Y  %H:%M:%S)",lt)

sys.stdout.write(t1.format(month[lt.tm_mon-1]))