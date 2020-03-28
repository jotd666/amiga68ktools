import wget,os,subprocess,shutil

s = """http://aminet.net/mods/inst/st-01.lha
http://aminet.net/mods/inst/st-02.lha
http://aminet.net/mods/inst/st-03.lha
http://aminet.net/mods/inst/st-04.lha
http://aminet.net/mods/inst/st-05.lha
http://aminet.net/mods/inst/st-06.lha
http://aminet.net/mods/inst/st-07.lha
http://aminet.net/mods/inst/st-08.lha
http://aminet.net/mods/inst/st-09.lha
http://aminet.net/mods/inst/st-10.lha
http://aminet.net/mods/inst/st-11.lha
http://aminet.net/mods/inst/st-12.lha
http://aminet.net/mods/inst/st-13.lha
http://aminet.net/mods/inst/st-14.lha
http://aminet.net/mods/inst/st-15.lha
http://aminet.net/mods/inst/st-16.lha
http://aminet.net/mods/inst/st-17.lha
http://aminet.net/mods/inst/st-18.lha
http://aminet.net/mods/inst/st-19.lha
http://aminet.net/mods/inst/st-20.lha
http://aminet.net/mods/inst/st-21.lha
http://aminet.net/mods/inst/st-22.lha
http://aminet.net/mods/inst/st-23.lha
http://aminet.net/mods/inst/st-24.lha
http://aminet.net/mods/inst/st-25.lha
http://aminet.net/mods/inst/st-26.lha
http://aminet.net/mods/inst/st-27.lha
http://aminet.net/mods/inst/st-28.lha
http://aminet.net/mods/inst/st-29.lha
http://aminet.net/mods/inst/st-30.lha
http://aminet.net/mods/inst/st-31.lha
http://aminet.net/mods/inst/st-32.lha
http://aminet.net/mods/inst/st-33.lha
http://aminet.net/mods/inst/st-34.lha
http://aminet.net/mods/inst/st-35.lha
http://aminet.net/mods/inst/st-36.lha
http://aminet.net/mods/inst/st-37.lha
http://aminet.net/mods/inst/st-38.lha
http://aminet.net/mods/inst/st-39.lha
http://aminet.net/mods/inst/st-40.lha
http://aminet.net/mods/inst/st-41.lha
http://aminet.net/mods/inst/st-42.lha
http://aminet.net/mods/inst/st-43.lha
http://aminet.net/mods/inst/st-44.lha
http://aminet.net/mods/inst/st-45.lha
http://aminet.net/mods/inst/st-46.lha
http://aminet.net/mods/inst/st-47.lha
http://aminet.net/mods/inst/st-48.lha
http://aminet.net/mods/inst/st-49.lha
http://aminet.net/mods/inst/st-50.lha
http://aminet.net/mods/inst/st-51.lha
http://aminet.net/mods/inst/st-52.lha
http://aminet.net/mods/inst/st-53.lha
http://aminet.net/mods/inst/st-54.lha
http://aminet.net/mods/inst/st-55.lha
http://aminet.net/mods/inst/st-56.lha
http://aminet.net/mods/inst/st-57.lha
http://aminet.net/mods/inst/st-58.lha
http://aminet.net/mods/inst/st-59.lha
http://aminet.net/mods/inst/st-60.lha
http://aminet.net/mods/inst/st-61.lha
http://aminet.net/mods/inst/st-62.lha
http://aminet.net/mods/inst/st-63.lha
http://aminet.net/mods/inst/st-64.lha
http://aminet.net/mods/inst/st-65.lha
http://aminet.net/mods/inst/st-66.lha
http://aminet.net/mods/inst/st-67.lha
http://aminet.net/mods/inst/st-68.lha
http://aminet.net/mods/inst/st-69.lha
http://aminet.net/mods/inst/st-70.lha
http://aminet.net/mods/inst/st-71.lha
http://aminet.net/mods/inst/st-72.lha
http://aminet.net/mods/inst/st-73.lha
http://aminet.net/mods/inst/st-74.lha
http://aminet.net/mods/inst/st-75.lha
http://aminet.net/mods/inst/st-76.lha
http://aminet.net/mods/inst/st-77.lha
http://aminet.net/mods/inst/st-78.lha
http://aminet.net/mods/inst/st-79.lha
http://aminet.net/mods/inst/st-80.lha
http://aminet.net/mods/inst/st-81.lha
http://aminet.net/mods/inst/st-82.lha
http://aminet.net/mods/inst/st-83.lha
http://aminet.net/mods/inst/st-84.lha
http://aminet.net/mods/inst/st-85.lha
http://aminet.net/mods/inst/st-86.lha
http://aminet.net/mods/inst/st-87.lha
http://aminet.net/mods/inst/st-88.lha
http://aminet.net/mods/inst/st-89.lha
http://aminet.net/mods/inst/st-90.lha
http://aminet.net/mods/inst/st-91.lha
http://aminet.net/mods/inst/st-92.lha
http://aminet.net/mods/inst/st-93.lha
http://aminet.net/mods/inst/st-94.lha
http://aminet.net/mods/inst/st-95.lha
http://aminet.net/mods/inst/st-96.lha
http://aminet.net/mods/inst/st-97.lha
http://aminet.net/mods/inst/st-98.lha
http://aminet.net/mods/inst/st-a0.lha
http://aminet.net/mods/inst/st-a1.lha
http://aminet.net/mods/inst/st-a2.lha
http://aminet.net/mods/inst/st-a3.lha
http://aminet.net/mods/inst/st-a4.lha
http://aminet.net/mods/inst/st-a5.lha
http://aminet.net/mods/inst/st-a6.lha
http://aminet.net/mods/inst/st-a7.lha
http://aminet.net/mods/inst/st-a8.lha
http://aminet.net/mods/inst/st-a9.lha
http://aminet.net/mods/inst/st-b0.lha
http://aminet.net/mods/inst/st-b1.lha
http://aminet.net/mods/inst/st-b2.lha
http://aminet.net/mods/inst/st-b3.lha
http://aminet.net/mods/inst/st-b4.lha
http://aminet.net/mods/inst/st-b5.lha
http://aminet.net/mods/inst/st-b6.lha""".split()

for u in s:
    target = os.path.join(r"K:\jff\AmigaHD\PROJETS\stxx",os.path.basename(u))
    target_dir = os.path.splitext(target)[0]
    if os.path.isdir(target_dir):
        pass
    else:
        if os.path.isfile(target):
            print("{} exists".format(target))
        else:
            try:
                wget.download(u,out=target)
            except Exception as e:
                print(u,e)
                pass
        rc = subprocess.call(["lha","x",target],cwd=os.path.dirname(target))
        if rc and os.path.isdir(target_dir):
            shutil.rmtree(target_dir,ignore_errors=True)
            print("unarchiving failed for {}".format(target))
