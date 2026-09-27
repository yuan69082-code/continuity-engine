"""Read existing profiles only; never rerun Engine or overwrite raw evidence."""
import hashlib,json,pathlib
HERE=pathlib.Path(__file__).parent
result={}
for label in ('recall-cpu-01','recall-cpu-after-01'):
    path=HERE/(label+'.trace.json')
    rows=json.loads(path.read_text(encoding='utf8'))
    preparations=[]
    for index,values in enumerate(rows):
        def pick(file,function):
            return next((v for v in values if file in v['file'] and v['function']==function),None)
        preparations.append(dict(index=index,
            prepare=pick('associative_recall_service.py','_prepare'),
            registry_read=pick('json_external_provider_repository.py','_read'),
            registry_safe=pick('json_external_provider_repository.py','_safe'),
            metadata={name:pick('pathlib',name) for name in ('is_symlink','exists','is_junction','lstat')}))
    result[label]=dict(raw=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),preparations=preparations)
with (HERE/'cpu-comparison.json').open('x',encoding='utf8') as out:
    json.dump(result,out,ensure_ascii=False,indent=2)
print(json.dumps({k:[dict(index=p['index'],prepare_ms=round(p['prepare']['total_seconds']*1000,3),
    safe_calls=p['registry_safe']['calls'],safe_ms=round(p['registry_safe']['total_seconds']*1000,3))
    for p in v['preparations']] for k,v in result.items()},ensure_ascii=False))
