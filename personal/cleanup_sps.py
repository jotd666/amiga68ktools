import json,filecmp,os

with open("dupes.json") as f:
    dupes = json.load(f)

dupes = [sorted(x) for x in dupes.values()]

for first,*others in dupes:
    for o in others:
        try:
            os.remove(o)
        except OSError as e:
            print("Argh: {}".format(e))

