import subprocess
print("building...")
while True:
    try:
        subprocess.check_call([r"make","-f","makefile_windows.mak"])
    except Exception:
        input("*** Press return to retry ***")
    break
import time
time.sleep(4)

