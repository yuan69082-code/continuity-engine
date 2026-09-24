"""W02-B non-authoritative recall policy and journal evidence.

This describes retrieval, never the truth of an input or a second memory store.
"""
from dataclasses import asdict, dataclass
import math
from .action_planning import digest
from .errors import CapabilityValidationError


@dataclass(frozen=True)
class RecallPolicy:
    candidate_limit: int = 60
    per_round_limit: int = 20
    max_rounds: int = 4
    latency_ms: int = 1000
    sufficient_roots: int = 4
    preference_minimum_roots: int = 3
    preference_require_positive_report: bool = True
    version: str = 'w02-recall-policy-v1'

    def __post_init__(self):
        if (type(self.candidate_limit) is not int or not 30 <= self.candidate_limit <= 80
                or any(type(v) is not int or v < 1 for v in
                       (self.per_round_limit,self.max_rounds,self.latency_ms,
                        self.sufficient_roots,self.preference_minimum_roots))
                or self.per_round_limit > self.candidate_limit
                or type(self.preference_require_positive_report) is not bool
                or self.version != 'w02-recall-policy-v1'):
            raise CapabilityValidationError('RECALL_POLICY_INVALID')

    def to_dict(self): return asdict(self)


def seal_record(payload):
    return {**payload, 'record_hash': digest(payload)}


def validate_record(record, *, operation=None, perception=None):
    required={'version','request_id','operation_id','subject_id','environment','perception_hash',
              'policy','assessment','rounds','status','stop_reason','elapsed_ms',
              'retrieved_count','model_calls','external_calls','snapshot_hash','record_hash','preference_candidates'}
    if not isinstance(record,dict) or set(record)!=required:
        raise CapabilityValidationError('RECALL_RECORD_SHAPE_INVALID')
    if (record['version']!='w02-recall-v1' or record['environment'] not in {'TEST','RESEARCH'}
            or record['status'] not in {'READY','BLOCKED'}
            or digest({k:v for k,v in record.items() if k!='record_hash'})!=record['record_hash']
            or not isinstance(record['rounds'],list)
            or not isinstance(record['assessment'],dict)
            or record['model_calls']!=0 or record['external_calls']!=0
            or type(record['retrieved_count']) is not int or record['retrieved_count']<0
            or type(record['elapsed_ms']) not in (int,float) or not math.isfinite(record['elapsed_ms']) or record['elapsed_ms']<0
            or not isinstance(record['preference_candidates'],list)
            or (record['status']=='READY') != (record['snapshot_hash'] is not None)):
        raise CapabilityValidationError('RECALL_RECORD_INVALID')
    policy=RecallPolicy(**record['policy'])
    if len(record['rounds'])>policy.max_rounds or record['retrieved_count']>policy.candidate_limit:
        raise CapabilityValidationError('RECALL_RECORD_BUDGET_INVALID')
    if operation is not None and (record['request_id'],record['operation_id'],record['subject_id'])!=(
            operation.request_id,operation.operation_id,operation.subject_id):
        raise CapabilityValidationError('RECALL_OPERATION_MISMATCH')
    if perception is not None:
        raw=perception.to_dict();raw.pop('continuity_context',None)
        if record['perception_hash']!=digest(raw):
            raise CapabilityValidationError('RECALL_INPUT_MISMATCH')


def validate_history(history):
    if not isinstance(history,tuple):
        raise CapabilityValidationError('RECALL_HISTORY_INVALID')
    for i,record in enumerate(history):
        validate_record(record)
        if i and (history[i-1]['status']=='READY' or any(record[k]!=history[0][k]
                for k in ('request_id','operation_id','subject_id','environment','perception_hash','policy'))):
            raise CapabilityValidationError('RECALL_HISTORY_BINDING_CHANGED')
