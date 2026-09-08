"""Read only the three fixed DOCX sources, preserving paragraph/table order."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

root=Path(__file__).resolve().parents[3];directory=Path(__file__).resolve().parent
source=json.loads((root/'docs/project_memory/p12_evidence/planning-source.json').read_text(encoding='utf-8'))
out=directory/'planning-read.json'
if out.exists():raise FileExistsError(out)
q=lambda name:'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'+name
result={}
for key,item in source.items():
    path=Path(item['source']);raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==item['sha256']
    with zipfile.ZipFile(path) as z:body=ET.fromstring(z.read('word/document.xml')).find(q('body'))
    blocks=[]
    for child in body:
        kind=child.tag.rsplit('}',1)[-1]
        if kind=='p':text=''.join(t.text or '' for t in child.iter(q('t')))
        elif kind=='tbl':
            text='\n'.join('\t'.join(''.join(t.text or '' for t in cell.iter(q('t')))
                for cell in row.findall(q('tc'))) for row in child.findall(q('tr')))
        else:continue
        if text.strip():blocks.append({'index':len(blocks),'type':kind,'text':text})
    result[key]={'source':str(path),'sha256':item['sha256'],'blocks':blocks}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for key,item in result.items():
    print(key,'blocks',len(item['blocks']))
    for b in item['blocks']:
        if any(k in b['text'] for k in ('P13','Expression','表达层','统一验收','Override','Keep')):
            print(b['index'],b['type'],b['text'])
