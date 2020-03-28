import re

r = re.compile("^(\d+)-(\d+)\s.*CD32: READ DATA")

input_file = r"C:\Users\Public\Documents\Amiga Files\WinUAE\winuaelog.txt"

previous_date = None
with open(input_file) as f:
    for line in f:
        m = r.match(line)
        if m:
            date = int(m.group(1))*1000 + int(m.group(2))
            if previous_date is not None:
                delta_date = date - previous_date
                status = "SHORT" if delta_date < 150 else "OK"
                print("{}: {}: {}".format(status,delta_date,line.strip()))
            previous_date = date