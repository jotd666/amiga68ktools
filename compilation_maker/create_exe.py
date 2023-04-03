import sys,os
from cx_Freeze import setup, Executable


# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "excludes": ["PyQt5"],
    "include_files":[("data","lib/data")]+[(os.path.join(os.pardir,"lib",x),("lib/"+x))
                for x in ("search.png","windows_explorer.png")]+[(x,x) for x in ["HDROOT_DEMO","data","gameinfo.csv"]],
#    "zip_include_packages": ["encodings", "PySide6"],
}

# base="Win32GUI" should be used only for Windows GUI app
base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="compilation_maker",
    version="0.1",
    description="Compilation Maker for AGS",
    options={"build_exe": build_exe_options},
    executables=[Executable("compilation_maker_gui.py", base=base)],
)