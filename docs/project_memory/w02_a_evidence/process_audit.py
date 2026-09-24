"""Read process ancestry and saved cleanup results; does not stop any process."""
import ctypes
from ctypes import wintypes
import datetime
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


class Entry(ctypes.Structure):
    _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),
        ('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),
        ('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
        ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),
        ('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]


def main():
    roots={}
    for path in HERE.glob('*.json'):
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,dict) and 'sourceBefore' in data and 'pid' in data:
            roots[data['pid']]=dict(label=path.stem,status=data.get('status'),exitCode=data.get('exitCode'))
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(),'PROCESS_SNAPSHOT_UNAVAILABLE')
    processes=[]
    try:
        entry=Entry();entry.dwSize=ctypes.sizeof(entry)
        more=kernel.Process32FirstW(handle,ctypes.byref(entry))
        while more:
            processes.append(dict(pid=entry.th32ProcessID,parentPid=entry.th32ParentProcessID,name=entry.szExeFile))
            more=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally:kernel.CloseHandle(handle)
    related=set(roots)
    while True:
        next_set=related|{p['pid'] for p in processes if p['parentPid'] in related}
        if next_set==related:break
        related=next_set
    observed=[p for p in processes if p['pid'] in related]
    selected=json.loads((HERE/'selected-runs.json').read_text(encoding='utf-8'))
    saved=[]
    for group in ('special','compatibility','full'):
        label=selected[group]
        if not label:continue
        for number,line in enumerate((HERE/(label+'.stdout.log')).read_text(encoding='utf-8').splitlines(),1):
            try:data=json.loads(line)
            except ValueError:continue
            if isinstance(data,dict) and ('childPid' in data or ('command' in data and '--phase' in data['command'])):
                saved.append(dict(label=label,line=number,record=data))
    result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),method='Windows Toolhelp process ancestry, no process mutation',
        runnerRoots=roots,aliveRelated=observed,allSelectedFinished=all(roots[p]['status']=='FINISHED' for p in roots),
        selectedChildResults=saved,cleanupPerformedBy='original bounded test controllers; communicate/wait/explicit STOP, not this audit',
        limitation='Point-in-time PID/parent snapshot plus recorded child exits; no claim about unrelated user processes. No unrelated processes or Temp artifacts removed.')
    label=sys.argv[1] if len(sys.argv)>1 else 'process-cleanup'
    assert label.replace('-','').isalnum()
    target=HERE/(label+'.json')
    assert not target.exists(), 'process evidence labels are immutable'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(aliveRelated=observed,selectedChildRecords=len(saved)),ensure_ascii=False))


if __name__=='__main__':main()
