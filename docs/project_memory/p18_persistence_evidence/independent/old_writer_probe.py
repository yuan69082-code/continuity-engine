"""Exact archived writer, current handshake tests: reconstruction, not old full run."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from test_p18_persistence import PersistenceTests
from continuity_engine.storage.json_repository import JsonSubjectStateRepository

snapshot=Path(__file__).resolve().parents[1]/'source-before/json_repository.py'
spec=importlib.util.spec_from_file_location('p18_archived_writer',snapshot)
archived=importlib.util.module_from_spec(spec);spec.loader.exec_module(archived)

def setup(self):
    original=JsonSubjectStateRepository._write_payload
    self.addCleanup(setattr,JsonSubjectStateRepository,'_write_payload',original)
    JsonSubjectStateRepository._write_payload=archived.JsonSubjectStateRepository._write_payload
    print(json.dumps({'reconstruction':'archived writer only; current release handshake',
        'snapshot':snapshot.as_posix(),'sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest()}))

selected={'test_actual_repository_reader_does_not_prevent_atomic_transition',
          'test_real_reader_blocks_no_new_effect_or_revision_after_release'}
methods={k:v for k,v in vars(PersistenceTests).items() if callable(v) and
         (not k.startswith('test_') or k in selected)}
methods['setUp']=setup
OldWriterEvidence=type('OldWriterEvidence',(unittest.TestCase,),methods)
