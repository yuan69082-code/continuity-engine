import json,pathlib,sys
HERE=pathlib.Path(__file__).resolve().parent
for name in sys.argv[1:]:
    rows=[]
    for p in (HERE/name).glob('process-*.json'):rows.extend(json.loads(p.read_text())['events'])
    rows.sort(key=lambda r:r['ns']);zero=rows[0]['ns'];held={};selected=[]
    for r in rows:
        key=(r['pid'],r['thread'],r.get('path_id'))
        if r['event']=='lock_acquired':held[key]=r
        if r['event']=='lock_released' and key in held:
            old=held.pop(key);ms=(r['ns']-old['ns'])/1e6
            if ms>30:selected.append(dict(event='lock_interval',pid=r['pid'],file=r['file'],path_id=r['path_id'],start_ms=(old['ns']-zero)/1e6,end_ms=(r['ns']-zero)/1e6,held_ms=ms))
        if r['event'] in ('injected_hold_start','injected_hold_end','lock_exception') or r.get('method') in ('control','_checkpoint_backoff'):
            selected.append({**r,'at_ms':(r['ns']-zero)/1e6})
    dest=HERE/(name+'.summary.json')
    with dest.open('x') as f:json.dump(selected,f,indent=2)
    print(name)
    for r in selected:
        if r.get('file')=='owner.lock' and r.get('event')=='lock_exception':continue
        print(json.dumps(r))
