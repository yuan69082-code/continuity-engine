"""Only registry metadata and rebuildable candidate cache. No operation ledger."""
import json,os,tempfile
from pathlib import Path
from threading import RLock
from continuity_engine.domain.action_planning import digest,exact,identifier
from continuity_engine.domain.external_capabilities import ProviderDescriptor,ProviderResult,ExternalCapabilityError
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.errors import CapabilityValidationError

_LOCK=RLock()


class JsonExternalProviderRepository:
    def __init__(self,root,*,subject_id,environment):
        identifier(subject_id)
        if environment not in ('TEST','RESEARCH'):raise ExternalCapabilityError('EXTERNAL_BOUNDARY')
        self.subject_id,self.environment=subject_id,environment
        self.root=Path(root)/'external-providers'/environment.lower()/digest(subject_id)[7:]
        self.registry_path=self.root/'registry.json';self.cache_path=self.root/'cache.json'

    def _empty(self,kind):
        return {'format':'p16-'+kind+'-v1','subject_id':self.subject_id,'environment':self.environment,'revision':0,'entries':[]}

    def _read(self,kind):
        path=self.registry_path if kind=='registry' else self.cache_path
        if not path.exists():return self._empty(kind)
        self._safe(path)
        try:
            data=json.loads(path.read_text(encoding='utf-8'));exact(data,{'document','hash'})
            document=exact(data['document'],{'format','subject_id','environment','revision','entries'})
            if data['hash']!=digest(document) or any(document[k]!=self._empty(kind)[k] for k in ('format','subject_id','environment')):
                raise ValueError()
            if type(document['revision']) is not int or document['revision']<0 or not isinstance(document['entries'],list):raise ValueError()
            keys=[]
            for entry in document['entries']:
                if kind=='registry':
                    exact(entry,{'descriptor','enabled'});d=ProviderDescriptor.from_dict(entry['descriptor']);keys.append(d.key)
                    if type(entry['enabled']) is not bool or (d.subject_id,d.environment)!=(self.subject_id,self.environment):raise ValueError()
                else:
                    exact(entry,{'request_id','cached_at','result'});value=ProviderResult.from_dict(entry['result']);keys.append(entry['request_id'])
                    parse_capability_datetime(entry['cached_at'])
                    if (value.subject_id,value.environment)!=(self.subject_id,self.environment) or value.capability_request_id!=entry['request_id']:raise ValueError()
            if len(keys)!=len(set(keys)) or len(keys)>256:raise ValueError()
            return document
        except (ValueError,TypeError,KeyError,CapabilityValidationError):raise ExternalCapabilityError('EXTERNAL_STORE_CORRUPT') from None

    @staticmethod
    def _safe(path):
        for p in (path,*path.parents):
            if p.is_symlink() or (p.exists() and getattr(p,'is_junction',lambda:False)()):
                raise ExternalCapabilityError('EXTERNAL_STORE_LINK_FORBIDDEN')

    def _write(self,kind,document):
        path=self.registry_path if kind=='registry' else self.cache_path;self._safe(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.p16-',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump({'document':document,'hash':digest(document)},f,ensure_ascii=False,sort_keys=True);f.flush();os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)

    @property
    def revision(self):return self._read('registry')['revision']
    def descriptors(self):return tuple((ProviderDescriptor.from_dict(e['descriptor']),e['enabled']) for e in self._read('registry')['entries'])
    def get(self,key):
        for d,enabled in self.descriptors():
            if d.key==key:return d,enabled
        raise ExternalCapabilityError('EXTERNAL_CONNECTOR_MISSING')
    def register(self,descriptor,*,expected_revision):
        d=ProviderDescriptor.from_dict(descriptor.to_dict())
        if (d.subject_id,d.environment)!=(self.subject_id,self.environment):raise ExternalCapabilityError('EXTERNAL_REGISTRY_BINDING')
        with _LOCK:
            data=self._read('registry')
            if data['revision']!=expected_revision:raise ExternalCapabilityError('EXTERNAL_REGISTRY_REVISION')
            for item in data['entries']:
                old=ProviderDescriptor.from_dict(item['descriptor'])
                if old.key==d.key:
                    if old!=d or not item['enabled']:raise ExternalCapabilityError('EXTERNAL_REGISTRY_IDENTITY_CONFLICT')
                    return
                if old.capability_ref==d.capability_ref:raise ExternalCapabilityError('EXTERNAL_CAPABILITY_IDENTITY_CONFLICT')
            if len(data['entries'])>=256:raise ExternalCapabilityError('EXTERNAL_REGISTRY_FULL')
            data['entries'].append({'descriptor':d.to_dict(),'enabled':True});data['revision']+=1;self._write('registry',data)
    def disable(self,key,*,expected_revision):
        with _LOCK:
            data=self._read('registry')
            if data['revision']!=expected_revision:raise ExternalCapabilityError('EXTERNAL_REGISTRY_REVISION')
            entry=next((e for e in data['entries'] if ProviderDescriptor.from_dict(e['descriptor']).key==key),None)
            if entry is None:raise ExternalCapabilityError('EXTERNAL_CONNECTOR_MISSING')
            if not entry['enabled']:return
            entry['enabled']=False;data['revision']+=1;self._write('registry',data)
    def cache(self,result,*,at):
        parse_capability_datetime(at)
        value=ProviderResult.from_dict(result.to_dict())
        if (value.subject_id,value.environment)!=(self.subject_id,self.environment):raise ExternalCapabilityError('EXTERNAL_CACHE_BINDING')
        with _LOCK:
            data=self._read('cache');entry={'request_id':value.capability_request_id,'cached_at':at,'result':value.to_dict()}
            old=next((e for e in data['entries'] if e['request_id']==value.capability_request_id),None)
            if old:
                if old['result']!=entry['result']:raise ExternalCapabilityError('EXTERNAL_CACHE_CONFLICT')
                return
            if len(data['entries'])>=256:raise ExternalCapabilityError('EXTERNAL_CACHE_FULL')
            data['entries'].append(entry);data['revision']+=1;self._write('cache',data)
    def cached(self):return tuple(self._read('cache')['entries'])
