# This Python file uses the following encoding: utf-8

import csv,os,collections,openpyxl

active_authors = {"Psygore","Wepl","StingRay","CFOU","GalahadFLT","Abaddon"}
d = {"retour  d'informations":2,"affecté":3, "nouveau":1, "confirmé":5, "suspendu":0}
keys = ['Identifiant','Projet','nb bugs','Résumé','Date de soumission','Mis à jour','Statut','Résolution','Assigné à']
width_dict = {'Identifiant':15, 'Projet':30, 'Résumé' : 90}
with open(os.path.join(os.getenv("USERPROFILE"),"Downloads","JOTD.csv"),encoding="utf-8") as f:
    b=f.read(1) # skip BOM
    cr = csv.DictReader(f)
    cr = list(cr)
    # now count how many bugs for each game
    bugcount = collections.Counter(row["Projet"] for row in cr)
    for row in cr:
        row['nb bugs'] = bugcount[row["Projet"]]

    # sort according to date, newest first
    # if row["Assigné à"] in ["","JOTD"]
    rows = sorted((row for row in cr if row["Assigné à"] not in active_authors),key=lambda x : (x['Mis à jour'],x["nb bugs"],d.get(x['Statut'],-1)),reverse=True)
    data = [keys] + [[row[k] for k in keys] for row in rows]

ox = openpyxl.Workbook()
ws = ox.active
for rn,row in enumerate(data,1):
    ws.append(row)
    cell = ws['A{}'.format(rn)]
    cell.hyperlink = "http://mantis.whdload.de/view.php?id={}".format(row[0])
    cell.style = "Hyperlink"
for i,k in enumerate(keys):
    w = width_dict.get(k)
    if w:
        ws.column_dimensions[chr(65 + i)].width = w

maxcolumnletter = openpyxl.utils.get_column_letter(ws.max_column)
ws.auto_filter.ref = 'A1:'+maxcolumnletter+str(len(ws['A']))

outname = "K:/whdload_bugs.xlsx"
ox.save(outname)
os.startfile(outname)