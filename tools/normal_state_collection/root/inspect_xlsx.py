"""Read source workbook XML without editing or executing source macros."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as E
import json
import sys

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def read_sheets(path):
    with ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(s.itertext()) for s in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rels={r.attrib['Id']: r.attrib['Target'] for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for s in E.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rels[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=[]
            for r in E.fromstring(z.read(target)).findall('s:sheetData/s:row',NS):
                cells={}
                for c in r.findall('s:c',NS):
                    v=c.find('s:v',NS)
                    raw=v.text if v is not None else None
                    if c.attrib.get('t')=='s' and raw is not None: value=strings[int(raw)]
                    elif c.attrib.get('t')=='inlineStr': value=''.join(c.find('s:is',NS).itertext())
                    else:
                        try: value=float(raw) if raw is not None else None
                        except ValueError: value=raw
                    if value is not None: cells[c.attrib['r']]=value
                if cells: rows.append(cells)
            yield s.attrib['name'],rows

if __name__=='__main__':
    for name, rows in read_sheets(Path(sys.argv[1])):
        print(json.dumps({'sheet':name,'rows':len(rows),'first':rows[:7],'last':rows[-1:]},ensure_ascii=False))
