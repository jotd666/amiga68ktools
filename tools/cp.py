import os,glob,shutil
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("source", help="source file/directory")
parser.add_argument("destination", help="destination file/directory")
parser.add_argument("-F","--flat", help="ignore source dirtree, copy flat",action="store_true")
parser.add_argument("-M","--move", help="move instead of copying",action="store_true")
parser.add_argument("-W","--wildcard", help="wildcards to consider",nargs="+")
args = parser.parse_args()

source_is_dir = os.path.isdir(args.source)
dest_is_dir = os.path.isdir(args.destination)

if source_is_dir:
    if not os.path.exists(args.destination):
        os.mkdir(args.destination)

    for root,dirs,files in os.walk(args.source):
        rel_root = root[len(args.source)+1:]


        for file in files:
            source = os.path.join(root,file)
            if args.flat:
                dest = os.path.join(args.destination,file)
            else:
                dest = os.path.join(args.destination,rel_root,file)

                destdir = os.path.dirname(dest)
                if not os.path.exists(destdir):
                    os.makedirs(destdir)
            if args.move:
                shutil.move(source,dest)
            else:
                shutil.copy(source,dest)

