from pathlib import Path
import tempfile,json,time
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
with tempfile.TemporaryDirectory(prefix="w04-4-measure-") as directory:
 f=W04EntryFixture(Path(directory));f.submit("A入口的私密选店资料。")
 f.configure("entry:B",read_from=("entry:B",));f.advance()
 totals={}
 def instrument(obj,name,key):
  original=getattr(obj,name)
  def measured(*args,**kwargs):
   start=time.perf_counter()
   try:return original(*args,**kwargs)
   finally:
    row=totals.setdefault(key,{"calls":0,"seconds":0});row["calls"]+=1;row["seconds"]+=time.perf_counter()-start
  setattr(obj,name,measured)
 for obj,name,key in [(f.core.router,"route","router"),(f.core.composer,"compose","composer"),(f.entries,"binding","binding"),(f.repo,"load","environment_load"),(f.entries,"origins","origin"),(f.app.ledger,"_load_operations","operations"),(f.app.ledger,"_load_capability_records","capability")]:
  if hasattr(obj,name):instrument(obj,name,key)
 try:f.submit("B入口自己的选店信息。",entry="entry:B");status="COMPLETED"
 except Exception as error:
  status=type(error).__name__
 operation=f.app.ledger.load_operation(f.last_request["requestId"])
 record=operation.domain_progress.recall_progress[-1] if operation.domain_progress.recall_progress else None
 print(json.dumps({"status":status,"measured_inclusive_overlapping":totals,"recall":record,"model_calls":len(f.provider.inputs),"effects":{k:p.effect_count for k,p in f.ports.items()}},ensure_ascii=False))
