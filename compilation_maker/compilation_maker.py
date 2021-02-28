import argparse,sys,os,itertools,glob
import create_launcher_data_cd32load,create_launcher_data_whd,install_ags_boot,find_best_image
from importlib import reload

def doit(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    # Do some argument parsing
    parser.add_argument("-r","--root-directory", type=str, required=True)
    parser.add_argument("-s","--subdir-pattern", type=str, required=True, default="GAMES",
    help="comma-separated names/patterns of sub dirs. Ex: 'GAME*,DEMOS'")
    parser.add_argument("-k","--kickstarts-directory", type=str, required=False)
    parser.add_argument("-d","--database", type=str, required=False)
    parser.add_argument("-m","--missing-database", type=str, required=False)
    parser.add_argument("-M","--master-quitkey", type=str, required=False)
    parser.add_argument("-p","--program", type=str, choices=["whdload","cd32load","cd32load_hd","jst"],
                    required=True,help="program to run & media type")
    args = parser.parse_args(argv)
    if args.database == args.missing_database:
        raise Exception("Database & missing database cannot be the same file")
    if not os.path.isdir(args.root_directory):
        raise Exception("Directory {} doesn't exist".format(args.root_directory))
    # we'll compute the pattern of subdirs here
    subdirs = [x[len(args.root_directory)+1:] for x in itertools.chain.from_iterable(glob.glob(os.path.join(args.root_directory,y)) for y in args.subdir_pattern.split(","))]


    install_ags_boot.doit(args.root_directory,kickstarts_dir = args.kickstarts_directory,master_quitkey = args.master_quitkey)
    if args.program=="whdload":
        create_launcher_data_whd.doit(args.root_directory,subdirs=subdirs,database_file=args.database,empty_database_file=args.missing_database)
    else:
        create_launcher_data_cd32load.doit(args.root_directory,subdirs=subdirs,database_file=args.database,
        empty_database_file=args.missing_database,hard_drive=args.program in ["cd32load_hd","jst"],use_jst=args.program == "jst")
    find_best_image.doit(args.root_directory)
if __name__ == '__main__':
    doit()
