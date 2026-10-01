"""32 fixed read-only comparisons in an isolated TEST root; not Engine timing."""
import ctypes,json,os,stat,tempfile,time
from pathlib import Path
from ctypes import wintypes
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

kernel=ctypes.WinDLL('kernel32',use_last_error=True)
attributes=kernel.GetFileAttributesW
attributes.argtypes=[wintypes.LPCWSTR];attributes.restype=wintypes.DWORD
def current(path):
    value=attributes(str(path))
    if value==0xffffffff:
        error=ctypes.get_last_error()
        if error in (2,3):return None
        raise ctypes.WinError(error)
    return value
with tempfile.TemporaryDirectory(prefix='w04-path-cost-') as root:
    fixture=W04EntryFixture(Path(root));path=fixture.repo.path
    paths=(path,*path.parents)
    rows=[]
    for strategy in ('lstat','attributes'):
        start=time.perf_counter();observed=[]
        for repetition in range(32):
            seen=[]
            for p in paths:
                if strategy=='lstat':
                    info=p.lstat();value=getattr(info,'st_file_attributes',0)
                else:value=current(p)
                seen.append(bool(value&0x400))
            observed.append(seen)
        rows.append(dict(strategy=strategy,iterations=32,components=len(paths),
                         elapsed_ms=(time.perf_counter()-start)*1000,observed_reparse=observed))
    assert rows[0]['observed_reparse']==rows[1]['observed_reparse']
    assert current(Path(root)/'missing') is None
    print(json.dumps(dict(rows=rows,current_query_each_iteration=True,content_or_permission_reuse=False)))
