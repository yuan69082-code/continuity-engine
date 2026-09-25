"""Host-neutral P16 ports. The Engine never receives an API key or SDK client."""
from typing import Protocol
from continuity_engine.domain.action_capability import InternalActionRequest,ActionReceipt,ReceiptQuery
from continuity_engine.domain.external_capabilities import ProviderDescriptor,ProviderResult
from continuity_engine.domain.external_absorption import ExternalRootProof


class CredentialBroker(Protocol):
    def authorize_reference(self,descriptor:ProviderDescriptor,*,at,purpose:str)->bool: ...
    def material_allowed(self,descriptor:ProviderDescriptor,value:object)->bool: ...


class ExternalPermissionPort(Protocol):
    def authorize(self,descriptor:ProviderDescriptor,*,at,purpose:str)->bool: ...


class MemoryProvider(Protocol):
    def query_receipt(self,request:InternalActionRequest)->ActionReceipt|ReceiptQuery: ...
    def execute_query(self,request:InternalActionRequest,descriptor:ProviderDescriptor)->ActionReceipt: ...
    def read_result(self,request:InternalActionRequest)->ProviderResult: ...


class KnowledgeProvider(MemoryProvider,Protocol):pass
class LocalMCPQueryProvider(MemoryProvider,Protocol):pass
class LocalSkillQueryProvider(MemoryProvider,Protocol):pass


class ExternalRootEvidencePort(Protocol):
    """Optional W02-C current-source evidence; no network implementation here."""
    def read_root(self,root_id:str)->ExternalRootProof: ...
