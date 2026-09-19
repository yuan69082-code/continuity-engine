"""Index existing safe telemetry without modifying raw evidence."""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
LABELS=('reader-before-01','native-before-02','old-writer-confirm-01','formal-final-02','p18-final-01')

def main():
    rows=[];files={}
    for label in LABELS:
        for suffix in ('.stdout.log','.stderr.log'):
            path=OUT/(label+suffix);files[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            for number,line in enumerate(path.read_text(encoding='utf8').splitlines(),1):
                start=line.find('{')
                if start<0:continue
                try:row=json.loads(line[start:])
                except ValueError:continue
                if not isinstance(row,dict):continue
                entries=[]
                if row.get('stage') in {'persistence-failure-before-unwind','native-exception-before-cleanup'}:entries.append(row)
                if row.get('exception'):entries.append(row)
                if isinstance(row.get('diagnostic'),dict):entries.append(row['diagnostic'])
                if isinstance(row.get('diagnostics'),str):
                    for inner in row['diagnostics'].splitlines():
                        try:value=json.loads(inner)
                        except ValueError:continue
                        if isinstance(value,dict):entries.append(value)
                for entry in entries:
                    rows.append({'file':path.name,'line':number,'record':entry,
                        'provenance':'Mixed run: classify by original test/record. Sharing Win5/32/33 is actual OS; errno28 and private-error probes are explicit injection; do not classify an entire run as real OS failure.'})
    target=OUT/'diagnostic-index-v2.json'
    with target.open('x',encoding='utf8') as f:
        json.dump({'rawHashes':files,'rows':rows,'historicalF2SystemCode':'UNKNOWN',
                   'supersedesClassificationOnly':{'file':'diagnostic-index.json','sha256':hashlib.sha256((OUT/'diagnostic-index.json').read_bytes()).hexdigest(),
                       'reason':'The initial index labeled mixed Native runs too broadly as real sharing experiments; raw logs and evidence unchanged.'},
                   'note':'Index only; original file/line and test identify real OS vs injected error. No historical OS codes reconstructed.'},f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(json.dumps({'records':len(rows),'files':len(files)}))

if __name__=='__main__':main()
