"""Locate new TEST setup failures without changing runtime behavior."""
import json, pathlib, sys, traceback
ROOT=pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests'))
from test_p18_storage_runtime import RuntimeStorageTests

class FixtureDiagnostic(RuntimeStorageTests):
    def fixture(self,**options):
        f=super().fixture(**options)
        original=f.work.dispatch
        def traced(request):
            try:return original(request)
            except BaseException as exc:
                chain=[];seen=set();cursor=exc
                while cursor is not None and id(cursor) not in seen:
                    seen.add(id(cursor))
                    chain.append({'type':type(cursor).__name__,'errno':getattr(cursor,'errno',None),
                        'winerror':getattr(cursor,'winerror',None),
                        'filenameLength':len(str(getattr(cursor,'filename',''))),
                        'parentExists':pathlib.Path(cursor.filename).parent.exists() if getattr(cursor,'filename',None) else None,
                        'frames':[{'file':pathlib.Path(fr.filename).name,'line':fr.lineno,'function':fr.name}
                                  for fr in traceback.extract_tb(cursor.__traceback__)]})
                    cursor=cursor.__cause__ or cursor.__context__
                print(json.dumps({'stage':'TEST_DISPATCH_FAILURE_BEFORE_CLEANUP','chain':chain}),flush=True)
                raise
        f.work.dispatch=traced
        return f

class ShortRootDiagnostic(FixtureDiagnostic):
    def setUp(self):
        import tempfile
        self.temp=tempfile.TemporaryDirectory(prefix='ps18-')
        self.root=pathlib.Path(self.temp.name)
        self.records=[]
