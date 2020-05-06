import os,sys,subprocess,shutil,glob,colorama
colorama.init()

tmparc = []
progdir = os.path.dirname(__file__)

local_mode = True
temp = r"K:\jff\AmigaHD\Download\whdload" if local_mode else os.getenv("TEMP")

c = colorama.Fore.LIGHTGREEN_EX

if len(sys.argv)<2:
    print("missing slave dev dir arg(s)")
try:

    for devdir in sys.argv[1:]: # r"C:\DATA\jff\AmigaHD\PROJETS\HDInstall\DONE\D\DataStormHDDev"
        tmpdir = os.path.join(temp,os.path.basename(devdir)[:-3])
        usrdir = os.path.join(devdir,"usr")

        gamename = os.path.basename(devdir)[:-5]
        print("Building {}...".format(gamename))
        output = subprocess.check_output("build.bat",shell=True,stdin=subprocess.DEVNULL,cwd=devdir)
        print(output.decode("ascii",errors="ignore"))
        print("Copying to user archive...")
        for slave in glob.glob(os.path.join(devdir,"*.slave")):
            print(slave)
            with open(slave,"rb") as f:
                contents = f.read()
                if b"DEBUG MODE" in contents or b"CHIP MODE" in contents:
                    raise Exception("Cannot distribute a 'DEBUG/CHIP MODE' slave")
            shutil.copy(slave,usrdir)
        for slave in glob.glob(os.path.join(devdir,"*.islave")):
            shutil.copy(slave,usrdir)
        for s in ["src","source"]:
            sd = os.path.join(usrdir,s)
            if os.path.isdir(sd):
                break
        else:
            os.mkdir(sd)

        for src in glob.glob(os.path.join(devdir,"*.s")):
            print(src)
            shutil.copy(src,sd)
        print("Creating archive...")
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        shutil.copytree(usrdir,tmpdir)
        arcname = gamename+".lha"
        arcfile = os.path.join(temp,arcname)
        if os.path.exists(arcfile):
            os.remove(arcfile)
        uaefs = os.path.join(tmpdir,"_UAEFSDB.___")
        if os.path.exists(uaefs):
            os.remove(uaefs)

##        if False: #local_mode:
##            pass
##        else:
##            shutil.copy(os.path.join(progdir,"lha_68k"),temp)
##            print(["cmd","/c",r"K:\jff\data\amiga_git_repos\amitools\lha.bat",arcname,os.path.basename(tmpdir)],temp)
##            subprocess.check_output(["cmd","/c",r"K:\jff\data\amiga_git_repos\amitools\lha.bat",arcname,os.path.basename(tmpdir)],cwd=temp)
##
##            #subprocess.check_output(["lha","a","-0",arcname,os.path.basename(tmpdir)],cwd=temp)
##            tmparc.append(tmpdir)
##            os.startfile(temp)
    if not local_mode:
        # send by e-mail

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email.utils import COMMASPACE, formatdate
        from email import encoders

        import smtplib
        fromaddr = 'jotd666@gmail.com'
        toaddrs  = ["release@whdload.de"]
        toaddrs = [fromaddr] # temp
        msg = MIMEMultipart()
        msg['From'] = fromaddr
        msg['To'] = COMMASPACE.join(toaddrs)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = "slave update"

        msg.attach( MIMEText("Enjoy!\n\nJFF\n") )

        for file in [arcfile]:
            part = MIMEBase('application', "octet-stream")
            part.set_payload( open(file,"rb").read() )
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"'
                           % os.path.basename(file))
            msg.attach(part)

        print("Sending e-mail...")
        username = fromaddr
        password = 'trou_du_cul'
        server = smtplib.SMTP('smtp.gmail.com:587')
        server.ehlo()
        server.starttls()
        server.login(username,password)
        server.sendmail(fromaddr, toaddrs, msg.as_string())
        server.quit()
        print("Done.")
except Exception as e:
    c = colorama.Fore.LIGHTRED_EX
    print("Error: {}{}{}".format(c,e,colorama.Fore.RESET))

print("{}Press a key to exit{}".format(c,colorama.Fore.RESET))
input()