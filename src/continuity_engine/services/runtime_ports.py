"""P18 host-neutral control identity, work and interruptible wait ports."""
from typing import Protocol
from threading import Event

from continuity_engine.domain.persistent_runtime import RuntimePrincipal, RuntimeNeed


class RuntimeIdentityPort(Protocol):
    def resolve(self, handle: str) -> RuntimePrincipal | None: ...


class RuntimeWorkPort(Protocol):
    def needs(self, at) -> tuple[RuntimeNeed,...]: ...
    def query(self, request): ...
    def dispatch(self, request): ...


class InterruptibleWait:
    """Bounded Event waiting, not busy polling or a model call timer."""
    def __init__(self):self.event=Event()
    def interrupt(self):self.event.set()
    def wait(self,seconds):
        self.event.wait(seconds)
        self.event.clear()


class RuntimeWorldBoundary:
    """Compose delivery scheduling and control with the existing P17 boundary.

    Historical receipts are still queried through P17 without new-execution
    authorization. The history port returns independently verified delivery time.
    No thought/body is examined and no alternate execution ledger is stored.
    """
    def __init__(self,delegate,*,guard,clock,delivery_policy,last_delivery):
        self.delegate=delegate;self.guard=guard;self.clock=clock
        self.delivery_policy=delivery_policy;self.last_delivery=last_delivery
    def ready(self,route):return self.delegate.ready(route)
    def capacity(self,route,request,limits):return self.delegate.capacity(route,request,limits)
    def authorize(self,route,request,*,purpose):
        if not self.delegate.authorize(route,request,purpose=purpose):return False
        if purpose=='execute' and route.capability_ref=='execution.write':
            return self.delivery_policy.allows(self.clock(),self.last_delivery(request))
        return True
    def recoverable(self,route):
        ready=self.delegate.recoverable(route)
        self.guard('final_world_dispatch')
        return ready
