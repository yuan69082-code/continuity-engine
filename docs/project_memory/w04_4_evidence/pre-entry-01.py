import json,tempfile
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture
with tempfile.TemporaryDirectory(prefix="w04-4-before-") as root:
 f=W02RecallFixture(root)
 request=f.message("周六去河边店还是山坡店？")
 before=f.runtime.subject_state().revision
 try:f.app.adapter.service.submit(request, entry_message={"entry_id":"entry:A"})
 except TypeError as exc:
  assert "entry_message" in str(exc)
  print(json.dumps({"status":"NOT_IMPLEMENTED","boundary":"normal C1 submit","error_type":type(exc).__name__,"reason":"entry_message not accepted","operation_created":f.app.ledger.load_operation(request["requestId"]) is not None,"revision_before":before,"revision_after":f.runtime.subject_state().revision}))
 else:raise AssertionError("expected missing entry metadata boundary")
