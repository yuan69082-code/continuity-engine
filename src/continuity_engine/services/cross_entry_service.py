"""Entry continuity projected from the existing journal, items and E5-A facts.

The host supplies verified account bindings, never subject intentions.  C1 owns
Thinking; P08/P13 owns expression; P17 owns every delivery and native receipt.
"""
from dataclasses import replace
import json

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.cross_entry import EntryBinding, EntryMessage, entry_time, reject, validate_entry_record
from continuity_engine.domain.environment_access import AttachmentKind
from .context_router_service import ContextPermissionDecision


class EntryPermission:
    def __init__(self, service, delegate):
        self.service, self.delegate = service, delegate
        self.policy_version = delegate.policy_version + ':entry-v1'

    def authorize_source(self, request, source_id, partition):
        return self.delegate.authorize_source(request, source_id, partition)

    def _decision(self, request, reference, original):
        allowed = original.allowed and self.service.reference_allowed(request.request_id, reference)
        return ContextPermissionDecision(allowed, original.reason_code if allowed else 'ENTRY_TRANSFER_DENIED', self.policy_version)

    def authorize_candidate(self, request, candidate):
        return self._decision(request, candidate, self.delegate.authorize_candidate(request, candidate))

    def authorize_reference(self, request, reference):
        return self._decision(request, reference, self.delegate.authorize_reference(request, reference))


class CrossEntryService:
    def __init__(self, *, access, clock, authorize_configuration, authorize_contact, authorize_read):
        self.access, self.clock = access, clock
        self.authorize_configuration = authorize_configuration
        self.authorize_contact, self.authorize_read = authorize_contact, authorize_read
        self.core = None
        self.interaction = None
        self.devices = {}
        self.routes = {}
        self.route_available = lambda entry, route: True
        self.native_thinking = None

    @staticmethod
    def _allowed(callback, *args):
        try:
            return callback(*args) is True
        except Exception:
            reject('PERMISSION_PORT_UNAVAILABLE')

    @property
    def ledger(self):
        return self.core.coordination._repository

    def configure(self, binding, *, expected_revision):
        binding = EntryBinding.from_dict(binding.to_dict())
        if not self._allowed(self.authorize_configuration, binding):
            reject('CONFIGURATION_DENIED')
        self.access.require(binding.use, kinds={AttachmentKind.MESSAGE_INGRESS, AttachmentKind.ENGINE_INTEGRATION})
        return self.access.repository.bind_entry(binding, expected_revision=expected_revision)

    def pause_contact(self, entry_id, paused, *, expected_revision):
        binding = self.binding(entry_id)
        if not self._allowed(self.authorize_configuration, binding):
            reject('CONFIGURATION_DENIED')
        return self.access.repository.contact_pause(binding.user_id, paused, expected_revision=expected_revision)

    def binding(self, entry_id):
        document = self.access.repository.load()
        return self._binding_in_document(entry_id,document)

    def _binding_in_document(self, entry_id, document):
        value = next((r for r in document.get('entry_bindings', []) if r['entry_id'] == entry_id), None)
        if value is None:
            reject('BINDING_MISSING')
        binding = EntryBinding.from_dict(value)
        now = self.clock()
        if not parse_capability_datetime(binding.verified_at) <= now < parse_capability_datetime(binding.expires_at):
            reject('BINDING_EXPIRED')
        self.access._require_from_document(binding.use,
            kinds={AttachmentKind.MESSAGE_INGRESS, AttachmentKind.ENGINE_INTEGRATION}, document=document)
        return binding

    def _binding_unchanged(self, binding):
        current = self.access.repository.load()
        if next((row for row in current.get('entry_bindings', [])
                 if row['entry_id'] == binding.entry_id), None) != binding.to_dict():
            reject('BINDING_CHANGED_DURING_CHECK')

    def validate_for_persistence(self, record):
        _, binding = validate_entry_record(record)
        self._binding_unchanged(binding)

    def current_record(self, operation):
        if operation is None or operation.entry_record is None:
            reject('OPERATION_MISSING')
        message, prior = validate_entry_record(operation.entry_record)
        current = self.binding(message.entry_id)
        if current != prior:
            reject('BOUND_CONTEXT_CHANGED')
        if not self._allowed(self.authorize_read, current):
            reject('READ_DENIED')
        self._binding_unchanged(current)
        return message, current

    def native_operation(self, thinking, action=None):
        """Reconstruct a view from the original ThinkSession and W03 sources.

        No synthetic user message and no parallel native request persistence.
        The final selected route is sealed by the original E5-A request.
        """
        from types import SimpleNamespace
        from continuity_engine.domain.cross_entry import ContactIntent
        from continuity_engine.domain.integration_results import format_contract_datetime
        result = thinking.session.result
        if result is None or result.contact_intent is None:
            reject('NATIVE_CONTACT_INTENT_REQUIRED')
        intent = ContactIntent.from_dict(result.contact_intent)
        # Reconstruct the original matter at the ThinkSession input revision,
        # not today's mutable active-item list. This is provenance only; NEW
        # execution still calls require_delivery/item for current eligibility.
        from continuity_engine.domain.unfinished_item import UnfinishedItem
        rows = None
        for update in self.core.subject_states.get_update_history(self.core.subject_id):
            if update.after_revision > thinking.perception.source_revision:
                continue
            for mutation in update.event.mutations:
                if mutation.field_path == 'continuity.item_records':
                    rows = mutation.value
        row = next((r for r in rows or () if r['item_id'] == intent.item_id), None)
        if row is None:
            reject('NATIVE_CONTACT_SOURCE_REQUIRED')
        item = UnfinishedItem.from_dict(row)
        roots = [root[6:] for root in item.source_roots if root.startswith('input:')]
        if not roots:
            reject('NATIVE_CONTACT_SOURCE_REQUIRED')
        original = self.ledger._load_operation_input(roots[0])
        if original is None or original.entry_record is None:
            reject('NATIVE_CONTACT_SOURCE_REQUIRED')
        _, source = validate_entry_record(original.entry_record)
        perception = thinking.perception
        request_id = 'native:' + perception.wake_session_id
        at = format_contract_datetime(perception.perceived_at)
        message = EntryMessage(source.entry_id, request_id, source.subject_account,
            source.recipient_account, source.audience, at, at, at, item_id=item.item_id,
            role='SUBJECT_CONTINUATION', preferred_entry_id=intent.entry_id)
        entry = dict(version='w04-entry-v1', message=message.to_dict(), binding=source.to_dict(),
            binding_hash=source.fingerprint, content_hash=digest(result.to_dict()))
        return SimpleNamespace(subject_id=self.core.subject_id, operation_id=request_id, request_id=request_id,
            entry_record=entry, domain_progress=SimpleNamespace(perception=perception,
                action=action or SimpleNamespace(context=SimpleNamespace(thinking_result=result))))

    @staticmethod
    def _perception_view(perception):
        from types import SimpleNamespace as View
        context = perception.continuity_context
        return View(source_revision=perception.source_revision, wake_session_id=perception.wake_session_id,
            perceived_at=perception.perceived_at, continuity_context=None if context is None else
            View(route=View(manifest=View(candidates=context.route.manifest.candidates)),
                 composition=View(snapshot=View(fragments=context.composition.snapshot.fragments))))

    @classmethod
    def _delivery_view(cls, operation):
        from types import SimpleNamespace as View
        progress = operation.domain_progress
        return View(request_id=operation.request_id, operation_id=operation.operation_id,
            subject_id=operation.subject_id, entry_record=operation.entry_record,
            domain_progress=None if progress is None else View(
                perception=cls._perception_view(progress.perception) if progress.perception else None,
                action=View(context=View(thinking_result=progress.action.context.thinking_result)) if progress.action else None))

    def delivery_operation(self, request_id):
        """No parallel fact: project the fully validated original records."""
        from types import SimpleNamespace as View
        from uuid import NAMESPACE_URL, uuid5
        if not request_id.startswith("native:"):
            rows = self.ledger._load_operations(_request_id=request_id, _projection=self._delivery_view)
            return rows[0] if rows else None
        if self.native_thinking is None:
            reject("NATIVE_HISTORY_NOT_READY")
        def project(session):
            if not session.completed_successfully or session.perception_snapshot is None:
                reject("NATIVE_HISTORY_UNCONFIRMED")
            return View(session=View(result=session.result), perception=self._perception_view(session.perception_snapshot))
        thinking = self.native_thinking._repository._load_projection(self.core.subject_id,
            str(uuid5(NAMESPACE_URL, "p14-think|" + request_id[len("native:"):])), project)
        return self.native_operation(thinking)

    def operation(self, request_id):
        if not request_id.startswith('native:'):
            return self.ledger.load_operation(request_id)
        from uuid import NAMESPACE_URL, uuid5
        from continuity_engine.domain.thinking import ThinkingExecutionResult
        if self.native_thinking is None:
            reject('NATIVE_HISTORY_NOT_READY')
        session = self.native_thinking.get_session(self.core.subject_id,
            str(uuid5(NAMESPACE_URL, 'p14-think|' + request_id[len('native:'):])) )
        if not session.completed_successfully or session.perception_snapshot is None:
            reject('NATIVE_HISTORY_UNCONFIRMED')
        return self.native_operation(ThinkingExecutionResult(session.perception_snapshot, session))

    def prepare(self, request, message):
        if not isinstance(message, EntryMessage):
            reject('MESSAGE_REQUIRED')
        if message.role == 'SUBJECT_CONTINUATION':
            reject('NATIVE_WAKE_REQUIRED')
        binding = self.binding(message.entry_id)
        if (request.identity.subject_id, request.identity.user_id) != (binding.use.subject_id, binding.user_id):
            reject('SUBJECT_USER_BINDING')
        expected_sender = binding.user_account if message.role == 'USER' else binding.subject_account
        if (message.sender_account != expected_sender or message.recipient_account !=
                (binding.subject_account if message.audience == 'PRIVATE' and message.role == 'USER' else binding.recipient_account)
                or message.audience != binding.audience or not binding.can_receive):
            reject('SENDER_RECIPIENT_BINDING')
        if not self._allowed(self.authorize_read, binding):
            reject('READ_DENIED')
        if entry_time(message.recorded_at) > self.clock():
            reject('UNTRUSTED_RECORD_TIME')
        if message.role == 'SUBJECT_CONTINUATION' and message.item_id is None:
            reject('CONTINUATION_ITEM_REQUIRED')
        if message.reply_to is not None:
            sent = self.ledger.load_capability_request(message.reply_to)
            if sent is None or sent.subject_id != binding.use.subject_id:
                reject('REPLY_REFERENCE')
            command = sent.step.input_payload or {}
            link = command.get('entry_delivery')
            if not link or link['entry_id'] != binding.entry_id or (message.item_id is not None and link['item_id'] != message.item_id):
                reject('REPLY_TOPIC_BINDING')
            if message.item_id is None and link['item_id'] is not None:
                message = replace(message, item_id=link['item_id'])
        if message.item_id is not None and message.role != 'SUBJECT_ECHO':
            self.item(message.item_id, binding)
        fact = request.platform_fact_package.facts[0]
        value = dict(version='w04-entry-v1', message=message.to_dict(), binding=binding.to_dict(),
                     binding_hash=binding.fingerprint, content_hash=fact.content_hash)
        old = self.ledger.load_operation(request.request_id)
        if old is not None and old.entry_record != value:
            reject('REQUEST_REBIND_FORBIDDEN')
        # Native echo and mirror events never become another user utterance.
        duplicate = next((op for op in self.ledger.list_operations()
            if op.entry_record is not None and op.request_id != request.request_id
            and op.entry_record['message']['entry_id'] == message.entry_id
            and op.entry_record['message']['external_message_id'] == message.external_message_id), None)
        if message.mirror_of is not None:
            duplicate = self.ledger.load_operation(message.mirror_of)
            if duplicate is None:
                reject('MIRROR_ROOT_MISSING')
        if duplicate is not None:
            _, original = self.current_record(duplicate)
            if (duplicate.entry_record['content_hash'] != fact.content_hash or
                    not self.transfer(original.entry_id, binding.entry_id)):
                reject('MIRROR_BINDING')
            return value, {'status': 'DUPLICATE_SOURCE', 'root_request_id': duplicate.request_id}
        if message.role == 'SUBJECT_ECHO':
            if message.reply_to is None:
                reject('ECHO_RECEIPT_REQUIRED')
            sent = self.ledger.load_capability_request(message.reply_to)
            from continuity_engine.domain.integration_hashing import calculate_content_hash
            if calculate_content_hash(sent.step.input_payload.get('text', '')) != fact.content_hash:
                reject('ECHO_CONTENT_BINDING')
            return value, {'status': 'SUBJECT_ECHO', 'send_request_id': message.reply_to}
        self._binding_unchanged(binding)
        return value, None

    def transfer(self, origin, destination):
        a = self.binding(origin)
        b = a if origin == destination else self.binding(destination)
        allowed = (a.user_id == b.user_id and (origin == destination or origin in b.read_from)
                and self._allowed(self.authorize_read, a)
                and (a is b or self._allowed(self.authorize_read, b)))
        self._bindings_unchanged((a, b))
        return allowed

    def _bindings_unchanged(self, bindings):
        current = {row['entry_id']: row for row in self.access.repository.load().get('entry_bindings', [])}
        if any(current.get(binding.entry_id) != binding.to_dict() for binding in bindings):
            reject('BINDING_CHANGED_DURING_CHECK')

    def item(self, item_id, binding):
        from continuity_engine.domain.unfinished_item import UnfinishedItem
        current = self.core.subject_states.load(binding.use.subject_id)
        row = next((r for r in current.continuity.item_records if r['item_id'] == item_id), None)
        if row is None:
            reject('ITEM_NOT_ACTIVE')
        item = UnfinishedItem.from_dict(row)
        if not item.willing or item.status in {'CANCELLED', 'COMPLETED'}:
            reject('ITEM_NOT_WILLING')
        for root in item.source_roots:
            if root.startswith('input:'):
                operation = self.ledger.load_operation(root[6:])
                _, source = self.current_record(operation)
                if not self.transfer(source.entry_id, binding.entry_id):
                    reject('ITEM_TRANSFER_DENIED')
        return item

    def reference_allowed(self, request_id, reference):
        target = self.ledger._load_operation_input(request_id)
        if target is None or target.entry_record is None:
            return True  # Original native/internal callers retain their policy.
        if reference.source_id == 'engine.subject-state':
            section = reference.stable_id.rsplit(':', 1)[-1]
            state, document = self.scoped_state(request_id, section=section)
            if section not in document or digest(document[section]) != reference.content_hash:
                return False
            # scoped_state has already checked every retained value's current
            # entry permission. Re-expanding the original field here would
            # both repeat that walk and reintroduce redacted item ancestry.
            return True
        else:
            origins = self.origins(reference.source_id, reference.stable_id)
        if not origins:
            return True
        message,prior=validate_entry_record(target.entry_record)
        destination = message.preferred_entry_id or prior.entry_id
        # One reference can inherit multiple entries. Use one pre-callback
        # document; each attachment gate still rereads after its callbacks and
        # all read-policy callbacks are followed by a final binding comparison.
        document=self.access.repository.load()
        ids=dict.fromkeys((prior.entry_id,destination,*sorted(origins)))
        checked={key:self._binding_in_document(key,document) for key in ids}
        current=checked[prior.entry_id]
        if current!=prior:reject('BOUND_CONTEXT_CHANGED')
        if not self._allowed(self.authorize_read,current):reject('READ_DENIED')
        end = checked[destination]
        for origin in origins:
            start = checked[origin]
            if (start.user_id != end.user_id or origin != destination and origin not in end.read_from
                    or not self._allowed(self.authorize_read, start) or not self._allowed(self.authorize_read, end)):
                return False
        self._bindings_unchanged(checked.values())
        return True

    def _provenance_operations(self):
        """Project only source links AFTER the entire current journal validates.

        This is a private read view, not a second record or eligibility cache.
        Omit irrelevant input disposition bodies before constructing isolated
        copies. The repository still reads current bytes on every invocation.
        """
        from types import SimpleNamespace as View
        def project(op):
            progress = op.domain_progress
            perception = (progress.perception or progress.input_preparation) if progress else None
            return View(request_id=op.request_id, entry_record=op.entry_record,
                event_ids=frozenset(f.source_event_id for f in perception.external_facts) if perception else frozenset(),
                evolution_event_id=op.evolution.event_id if op.evolution else None)
        return self.ledger._load_operations(_projection=project)

    def origins(self, source_id, stable_id, _path=frozenset(), _walk=None):
        """Reconstruct original provenance, sharing reads only within this walk.

        Each public call starts afresh. No permission or source eligibility is
        memoized; Router/Composer/consumption still run their current checks.
        A diamond in the immutable provenance graph is not a new independent
        source and need not parse/project the same ancestors repeatedly.
        """
        walk = {} if _walk is None else _walk
        key = (source_id, stable_id)
        if key in _path:
            reject('SOURCE_PROVENANCE_CYCLE')
        if key in walk:
            return set(walk[key])
        path = _path | {key}
        inherited = set()
        roots = set()
        if source_id == 'engine.subject-state':
            state = self.core.subject_states.load(self.core.subject_id)
            inherited.update(self._state_origins(stable_id.rsplit(':', 1)[-1], state.revision,
                                                None, walk, path))
        elif source_id in {'engine.current-input', 'engine.input-history'}:
            roots.add('input:' + stable_id.removeprefix('input:'))
        elif source_id == 'engine.memory':
            roots.update(self.core.memory.load_memory(self.core.subject_id, stable_id).root_evidence_ids)
        elif source_id in {'engine.derived-summary', 'engine.derived-summaries'}:
            roots.update(self.core.memory.load_summary(self.core.subject_id, stable_id).root_evidence_ids)
        elif source_id == 'engine.timeline':
            roots.add('event:' + stable_id)
        elif source_id == 'engine.execution-results' and stable_id.startswith('execution:'):
            request = self.ledger.load_capability_request(stable_id[len('execution:'):])
            if request is None:
                reject('RESULT_ROOT_MISSING')
            link = (request.step.input_payload or {}).get('entry_delivery')
            if link is not None:
                roots.add('input:' + link['request_id'])
                if link['request_id'].startswith('native:'):
                    operation = self.delivery_operation(link['request_id'])
                    inherited.add(operation.entry_record['message']['entry_id'])
                    inherited.update(self._context_origins(operation.domain_progress.perception.continuity_context,
                                                           walk, path))
            elif request.capability_type.startswith('device.'):
                # A history query/screenshot is still from its bound entry,
                # even though it has no message-send link. Match trusted
                # physical/account/session identities, not display names.
                from continuity_engine.domain.device_operation import DeviceCommand
                use=DeviceCommand.from_dict(request.step.input_payload).observation.use
                fields=('subject_id','environment','host_id','generation','channel_id',
                        'software_id','device_id','account_id','session_id')
                identity=tuple(getattr(use,key) for key in fields)
                if 'operations' not in walk:
                    walk['operations']=self._provenance_operations()
                bindings=list(self.access.repository.load().get('entry_bindings',[]))
                bindings.extend(op.entry_record['binding'] for op in walk['operations'] if op.entry_record is not None)
                for value in bindings:
                    binding=EntryBinding.from_dict(value)
                    if any(candidate is not None and tuple(getattr(candidate,key) for key in fields)==identity
                           for candidate in (binding.use,binding.send_use)):
                        inherited.add(binding.entry_id)
        if not roots:
            walk[key]=frozenset(inherited)
            return set(inherited)
        if 'operations' not in walk:
            walk['operations'] = self._provenance_operations()
        operations = walk['operations']
        # Input IDs do not need an Event-history scan. Only event ancestors can
        # contain an item update that adds more roots. This omits no root check.
        updates = ()
        if any(root.startswith('event:') for root in roots):
            if 'updates' not in walk:
                walk['updates'] = self.core.subject_states.get_update_history(self.core.subject_id)
            updates = walk['updates']
        for update in updates:
            if 'event:' + update.event.event_id not in roots:
                continue
            think_id = update.event.metadata.get('think_id')
            if think_id is not None:
                if self.native_thinking is None:
                    reject('SOURCE_THINKING_NOT_READY')
                def references(session):
                    perception = session.perception_snapshot
                    if perception is None or perception.continuity_context is None:
                        reject('SOURCE_THINKING_UNCONFIRMED')
                    return perception.continuity_context.composition.snapshot.fragments
                selected = self.native_thinking._repository._load_projection(
                    self.core.subject_id, think_id, references)
                for reference in selected:
                    inherited.update(self._fragment_origins(reference, walk, path))
            for mutation in update.event.mutations:
                if mutation.field_path == 'continuity.item_records':
                    for row in mutation.value:
                        roots.update(row['source_roots'])
        result = set(inherited)
        for op in operations:
            if op.entry_record is None:
                continue
            if ('input:' + op.request_id in roots or any('event:' + e in roots for e in op.event_ids)
                    or op.evolution_event_id is not None and 'event:' + op.evolution_event_id in roots):
                result.add(op.entry_record['message']['entry_id'])
        walk[key] = frozenset(result)
        return result

    @staticmethod
    def _lineage_node(value, origins, previous=None):
        """Ephemeral value lineage from actual FieldChanges, never a state store.

        Retaining a value (including SET/APPEND) retains its earlier sources.
        A new writer cannot relabel the unchanged members of a list or object.
        """
        if previous is not None and previous[0] == value:
            return previous
        if isinstance(value, list):
            old = previous[2] if previous is not None and isinstance(previous[0], list) else ()
            children = [CrossEntryService._lineage_node(v, origins, next((n for n in old if n[0] == v), None))
                        for v in value]
        elif isinstance(value, dict):
            old = previous[2] if previous is not None and isinstance(previous[0], dict) else {}
            children = {k: CrossEntryService._lineage_node(v, origins, old.get(k)) for k, v in value.items()}
        else:
            children = None
        if children:
            nodes = children.values() if isinstance(children, dict) else children
            origins = set().union(*(n[1] for n in nodes))
        return (value, frozenset(origins), children)

    @staticmethod
    def _node_origins(node, selected=None):
        value, roots, children = node
        if selected is None or children is None or not children:
            return set(roots)
        if isinstance(value, list):
            nodes = children if selected is None else [n for n in children if n[0] in selected]
        else:
            nodes = children.values() if selected is None else [n for k, n in children.items() if k in selected]
        return set().union(*(CrossEntryService._node_origins(n) for n in nodes))

    def _state_lineage(self, revision, walk, path, section=None):
        key = ('state-lineage', revision, section)
        if key in walk:
            return walk[key]
        if key in path:
            reject('SOURCE_PROVENANCE_CYCLE')
        if 'updates' not in walk:
            walk['updates'] = self.core.subject_states.get_update_history(self.core.subject_id)
        fields = {}
        for update in walk['updates']:
            if update.after_revision > revision:
                continue
            for change in update.changes:
                if section is not None and change.field_path.split('.', 1)[0] != section:
                    continue
                prior = fields.get(change.field_path)
                if prior is None:
                    prior = self._lineage_node(change.before, ())
                if prior[0] != change.before:
                    reject('STATE_SOURCE_HISTORY_CHANGED')
                roots = self.origins('engine.timeline', update.event.event_id, path | {key}, walk)
                fields[change.field_path] = self._lineage_node(change.after, roots, prior)
            # A later Event may refer to the ThinkSession at this exact older
            # revision. Reuse the already reconstructed prefix within this
            # same validated walk, rather than rebuilding that history again.
            # Nodes are immutable for the walk; no current grant is stored.
            walk[('state-lineage', update.after_revision, section)] = fields.copy()
        walk[key] = fields
        return fields

    def _state_origins(self, section, revision, selected, walk, path):
        roots = set()
        for field, node in self._state_lineage(revision, walk, path, section).items():
            area, name = field.split('.', 1)
            if area != section or selected is not None and name not in selected:
                continue
            value = selected.get(name) if selected is not None else None
            if field == 'continuity.item_records' and isinstance(value, dict):
                # The bounded current projection exposes only these actual
                # items; redacted/unselected records are not model evidence.
                selected_ids = {row['item_id'] for row in value.get('next', [])}
                for child in node[2]:
                    if child[0]['item_id'] in selected_ids:
                        roots.update(self._node_origins(child))
                continue
            # Bounded core projections have a different shape from the original
            # field: conservatively retain that field's complete ancestry.
            exact_shape = isinstance(node[0], list) and isinstance(value, list)
            roots.update(self._node_origins(node, value if exact_shape else None))
        return roots

    def _fragment_origins(self, fragment, walk, path):
        if fragment.source_id != 'engine.subject-state':
            return self.origins(fragment.source_id, fragment.stable_source_id, path, walk)
        try:
            revision = int(fragment.version.rsplit('revision:', 1)[1])
            selected = json.loads(fragment.content)
        except (ValueError, IndexError, TypeError):
            reject('STATE_SOURCE_VERSION_MISSING')
        if not isinstance(selected, dict):
            reject('STATE_SOURCE_CONTENT_INVALID')
        return self._state_origins(fragment.stable_source_id.rsplit(':', 1)[-1], revision, selected, walk, path)

    def _context_origins(self, context, walk, path=frozenset()):
        roots = set()
        for fragment in context.composition.snapshot.fragments:
            roots.update(self._fragment_origins(fragment, walk, path))
        return roots

    def scoped_state(self, request_id, *, section=None):
        """Read projection only; private topic fields never change the Subject."""
        from continuity_engine.domain.dynamic_mind import context_state_document
        state = self.core.subject_states.load(self.core.subject_id)
        document = context_state_document(state)
        if section is not None:
            document = {section: document[section]} if section in document else {}
        operation = self.ledger._load_operation_input(request_id)
        if operation is None or operation.entry_record is None:
            if request_id.startswith('native:') and 'identity' in document:
                options = []
                for row in self.access.repository.load().get('entry_bindings', []):
                    try:
                        binding = self.binding(row['entry_id'])
                        allowed = self._allowed(self.authorize_read, binding)
                    except Exception:
                        allowed = False
                    if allowed:
                        options.append(dict(entry_id=binding.entry_id, user_id=binding.user_id,
                            can_initiate=binding.can_initiate and binding.contact_enabled,
                            read_from=list(binding.read_from), verified_at=binding.verified_at,
                            expires_at=binding.expires_at))
                document['identity']['message_entry_options'] = options
            return state, document
        before = self.access.repository.load()
        message, prior = validate_entry_record(operation.entry_record)
        checked = {}
        def binding_for(entry_id):
            if entry_id not in checked:
                checked[entry_id] = self._binding_in_document(entry_id, before)
            return checked[entry_id]
        binding = binding_for(prior.entry_id)
        if binding != prior:
            reject('BOUND_CONTEXT_CHANGED')
        if not self._allowed(self.authorize_read, binding):
            reject('READ_DENIED')
        destination = message.preferred_entry_id or binding.entry_id
        # This one read-only projection can contain many fields from the same
        # entry. Authorize that entry once for this projection, not once per
        # field. Nothing survives the call; Router/Composer and consumption each
        # invoke a new projection and recheck current bindings/permissions.
        transfers = {}
        def readable(origin):
            if origin not in transfers:
                start, end = binding_for(origin), binding_for(destination)
                transfers[origin] = (start.user_id == end.user_id
                    and (origin == destination or origin in end.read_from)
                    and self._allowed(self.authorize_read, start)
                    and (start is end or self._allowed(self.authorize_read, end)))
            return transfers[origin]
        items = state.continuity.item_records if 'continuity' in document else ()
        kept = []
        for item in items:
            origins = set()
            for root in item['source_roots']:
                if root.startswith('input:'):
                    origins.update(self.origins('engine.current-input', root))
                elif root.startswith('event:'):
                    origins.update(self.origins('engine.timeline', root[6:]))
                elif root.startswith('memory:'):
                    origins.update(self.origins('engine.memory', root[7:]))
            if all(readable(origin) for origin in origins):
                kept.append(item)
        if items:
            projection = document['continuity']['item_records']
            projection['state_hash'] = digest(kept)
            projection['active_count'] = len(kept)
            ordered = sorted(kept, key=lambda row: row['item_id'] != message.item_id)
            projection['next'] = [{key: row[key] for key in ('item_id', 'title', 'status', 'next_step')}
                                  for row in ordered[:3]]
            if len(kept) != len(items):
                document['continuity']['entry_redacted_items'] = len(items) - len(kept)
        # Evolved fields keep their original update provenance.  Do not expose
        # a restricted entry merely because it has since become internal state.
        # A reference checks its own section, not five unrelated sections.
        # The repository still validates the complete current history; any
        # ancestor section actually read by Thinking is followed recursively.
        for field, node in self._state_lineage(state.revision, {}, frozenset(), section).items():
            if field == 'continuity.item_records':
                continue
            section, name = field.split('.', 1)
            if section not in document or name not in document[section]:
                continue
            if isinstance(node[0], list) and isinstance(document[section][name], list):
                document[section][name] = [n[0] for n in node[2]
                    if all(readable(origin) for origin in self._node_origins(n))]
            elif not all(readable(origin) for origin in self._node_origins(node)):
                document[section].pop(name, None)
                document[section].setdefault('entry_unavailable_fields', []).append(name)
        if self.access.repository.load() != before:
            reject('BINDING_CHANGED_DURING_CHECK')
        return state, document

    def require_delivery(self, operation, destination, *, historical=False):
        message, source = self.current_record(operation)
        target = source if destination == source.entry_id else self.binding(destination)
        # current_record has just authorized source. Check the target and scope
        # in this same boundary rather than recursively repeating both checks.
        if (source.user_id != target.user_id
                or source.entry_id != destination and source.entry_id not in target.read_from
                or source is not target and not self._allowed(self.authorize_read, target)):
            reject('CONTACT_TRANSFER_DENIED')
        if not historical:
            self.core.subject_states.require_active(self.core.subject_id, self.core.environment)
            if (not target.can_initiate or not target.contact_enabled or target.send_use is None
                    or target.user_id in self.access.repository.load().get('contact_pauses', [])
                    or not self._allowed(self.authorize_contact, target)):
                reject('CONTACT_DENIED')
            if message.item_id is not None:
                self.item(message.item_id, target)
        return target

    def delivery_current(self, request, command, *, purpose):
        before = self.access.repository.load()
        link = command.entry_delivery
        operation = self.delivery_operation(link['request_id'])
        binding = self.require_delivery(operation, link['entry_id'], historical=purpose == 'consume')
        if binding.fingerprint != link['binding_hash']:
            reject('DELIVERY_BINDING_STALE')
        if (command.observation.use != binding.send_use
                or request.choice.decision_id != 'c1:' + digest(operation.operation_id)[7:]
                or link['inquiry_id'] != operation.request_id):
            reject('DELIVERY_BINDING')
        progress = operation.domain_progress
        result = progress.action.context.thinking_result if progress and progress.action else None
        if result is None or command.text != result.result_summary:
            reject('DELIVERY_NOT_FORMED_EXPRESSION')
        message = EntryMessage.from_dict(operation.entry_record['message'])
        expected_item = message.item_id or ('matter:' + digest(operation.request_id)[7:]
                                           if result.suggest_future_user_contact else None)
        if link['item_id'] != expected_item:
            reject('DELIVERY_ITEM_BINDING')
        # Revalidate every selected source for the selected destination. The
        # destination was used during preparation, not added after an answer.
        context = progress.perception.continuity_context
        if context is None:
            reject('DELIVERY_CONTEXT_MISSING')
        origins = self._context_origins(context, {})
        # Raw, Memory and Summary references to the same entry share one
        # transfer boundary in THIS check, not three independent grants.
        origins.difference_update((message.entry_id, binding.entry_id))
        if not all(self.transfer(origin, binding.entry_id) for origin in origins):
            reject('DELIVERY_SOURCE_DENIED')
        # All permission/attachment callbacks have now returned. Re-read the
        # original control document; no callbacks follow this comparison.
        after = self.access.repository.load()
        if before != after:
            reject('BINDING_CHANGED_DURING_CHECK')

    def independent_inquiry(self, prior, current):
        """Two formed questions, not transport replay or a general retry grant.

        Both original E5-A commands and their original Thinking records bind
        this classification. All current execution gates still run in P17.
        """
        from continuity_engine.domain.device_operation import DeviceCommand
        old = DeviceCommand.from_dict(prior.step.input_payload)
        new = DeviceCommand.from_dict(current.step.input_payload)
        sends = {'message.send.api', 'message.send.ui'}
        if old.operation not in sends or new.operation not in sends:
            return False
        a, b = old.entry_delivery, new.entry_delivery
        if (a is None or b is None or a['item_id'] is None or
                a['item_id'] != b['item_id'] or a['entry_id'] != b['entry_id'] or
                a['inquiry_id'] == b['inquiry_id'] or a['request_id'] == b['request_id'] or
                prior.subject_id != current.subject_id or
                prior.choice.environment != current.choice.environment):
            return False
        for request, command, link in ((prior, old, a), (current, new, b)):
            operation = self.delivery_operation(link['request_id'])
            if operation is None or operation.subject_id != request.subject_id:
                return False
            result = operation.domain_progress.action.context.thinking_result
            if (result is None or result.should_wait or not result.suggest_future_user_contact
                    or command.text != result.result_summary
                    or link['inquiry_id'] != operation.request_id
                    or request.choice.decision_id != 'c1:' + digest(operation.operation_id)[7:]):
                return False
            message, _ = validate_entry_record(operation.entry_record)
            if message.item_id != link['item_id']:
                return False
        return True

    def receive(self, payload, message):
        if self.interaction is None:
            reject('INTERACTION_NOT_READY')
        with self.ledger._verified_operation_reads(), self.ledger._verified_capability_reads():
            return self.interaction.submit(payload, entry_message=message)

    def adopt_matter(self, request_id):
        """Adopt a formed subject intention via W03, not from ingress text alone."""
        from continuity_engine.domain.unfinished_item import UnfinishedItem
        from continuity_engine.domain.integration_results import IntegrationOperationStage
        operation = self.operation(request_id)
        message, binding = self.current_record(operation)
        if operation.stage is not IntegrationOperationStage.COMPLETED:
            reject('MATTER_THINKING_NOT_COMPLETED')
        result = operation.domain_progress.action.context.thinking_result
        if not result.suggest_future_user_contact or result.should_wait:
            reject('MATTER_NOT_DECIDED')
        if message.item_id is not None:
            return self.item(message.item_id, binding)
        item_id = 'matter:' + digest(request_id)[7:]
        item = UnfinishedItem(item_id, operation.subject_id, binding.use.environment,
            result.result_summary, ('input:' + request_id,), True, 'Formed subject contact intention',
            'NORMAL', None, 'awaiting_user_answer', 'Reevaluate contact or wait', 'WAITING',
            operation.domain.response_completed_at, operation.domain.response_completed_at)
        self.core.unfinished.submit(item, command_id='entry:' + request_id,
            expected_revision=operation.input_revision, context=operation.domain_progress.perception.continuity_context,
            reason='Preserve the subject-decided unanswered question')
        return item

    def delivery_evidence(self, send_request, query_ids):
        """Project typed delivery observations from original E5-A query facts.

        Inspect never starts a query. A caller supplies already executed query
        identities; each is rechecked for current source/read permission here.
        An arbitrary receipt, account or same-root substitute is not evidence.
        """
        import json
        from continuity_engine.domain.device_operation import DeviceCommand
        command = DeviceCommand.from_dict(send_request.step.input_payload)
        link = command.entry_delivery
        binding = self.require_delivery(self.delivery_operation(link['request_id']), link['entry_id'], historical=True)
        result = dict(delivered='NO_EVIDENCE', read='NO_EVIDENCE', observations=[])
        for query_id in dict.fromkeys(query_ids):
            request = self.core.execution.request(query_id)
            query = DeviceCommand.from_dict(request.step.input_payload)
            if query.operation != 'query':
                reject('DELIVERY_EVIDENCE_QUERY_REQUIRED')
            scope = query.history_scope()
            use = query.observation.use
            expected = binding.send_use
            if (scope.object_id != send_request.capability_request_id or
                    any(getattr(use, field) != getattr(expected, field) for field in
                        ('subject_id', 'environment', 'software_id', 'device_id', 'account_id', 'session_id'))):
                reject('DELIVERY_EVIDENCE_BINDING')
            device = self.devices[binding.entry_id]
            evidence = device.inspect(query_id)
            if evidence['status'] != 'SUCCEEDED':
                reject('DELIVERY_EVIDENCE_UNCONFIRMED')
            for record in evidence['result']['records']:
                try:
                    claim = json.loads(record['content'])
                except (TypeError, ValueError):
                    reject('DELIVERY_EVIDENCE_SHAPE')
                if (not isinstance(claim, dict) or set(claim) !=
                        {'version', 'request_id', 'entry_id', 'sender', 'recipient', 'status'} or
                        claim['version'] != 'w04-delivery-observation-v1' or
                        claim['request_id'] != send_request.capability_request_id or
                        claim['entry_id'] != binding.entry_id or claim['sender'] != binding.subject_account or
                        claim['recipient'] != binding.recipient_account or claim['status'] not in {'DELIVERED', 'READ'}):
                    reject('DELIVERY_EVIDENCE_BINDING')
                result['delivered'] = 'EVIDENCED'
                if claim['status'] == 'READ':
                    result['read'] = 'EVIDENCED'
                result['observations'].append(dict(status=claim['status'], source_id=record['source_id'],
                    root_id=record['root_id'], version=record['version'], occurred_at=record['occurred_at'],
                    query_request_id=query_id, receipt_hash=evidence['receipt_hash']))
        return result

    def inspect(self, request_id, *, evidence_requests=()):
        """Read stored facts only. No observation, delivery, task or learning work."""
        operation = self.operation(request_id)
        message, binding = self.current_record(operation)
        requests = self.core.coordination.action_requests_by_decision('c1:' + digest(operation.operation_id)[7:])
        delivery = []
        for request in requests:
            if not (request.step.input_payload or {}).get('entry_delivery'):
                continue
            attempts = self.core.coordination.action_attempts(request, receipt_verifier=self.core.execution.bindings()[list(self.core.execution.routes).index(request.capability_type)].adapter)
            last = attempts[-1].result if attempts else None
            receipt = last.receipt if last else None
            observed = self.delivery_evidence(request, evidence_requests) if evidence_requests else {}
            delivery.append({'request_id': request.capability_request_id,
                'status': 'SENT' if receipt and receipt.status == 'SUCCEEDED' else
                          'FAILED' if receipt and receipt.status == 'FAILED_TERMINAL' else 'UNKNOWN',
                'receipt_hash': receipt.canonical_hash() if receipt else None,
                'delivered': 'NO_EVIDENCE', 'read': 'NO_EVIDENCE', **observed,
                'reply': 'ANSWER_RECORDED' if any(op.entry_record is not None and
                    op.entry_record['message']['role'] == 'USER' and
                    op.entry_record['message']['reply_to'] == request.capability_request_id
                    for op in self.ledger.list_operations()) else 'UNANSWERED'})
        return {'request_id': request_id, 'subject_id': operation.subject_id,
                'entry': binding.entry_id, 'item_id': message.item_id,
                'source': message.to_dict(), 'operation_stage': getattr(getattr(operation, 'stage', None), 'value', 'NATIVE_THINKING_COMPLETED'),
                'deliveries': delivery}


class EntryDecisionPolicy:
    """Bind the already formed P08/P13 expression to a currently legal route."""
    def __init__(self, service, delegate):
        self.service, self.delegate = service, delegate
        self.producer_id = delegate.producer_id
        self._prepared = {}

    def choose(self, operation, context, thinking, action):
        original = self.delegate.choose(operation, context, thinking, action)
        if original is None:
            return original
        result = thinking.session.result
        if operation.request_id.startswith('native:') and result.contact_intent is not None:
            operation = self.service.native_operation(thinking, action)
        if getattr(operation, 'entry_record', None) is None:
            return original
        message = EntryMessage.from_dict(operation.entry_record['message'])
        existing = self.service.core.coordination.action_requests_by_decision(original.decision_id)
        if existing:
            choice = existing[0].choice
            for step in choice.steps:
                link = (step.input_payload or {}).get('entry_delivery')
                if link and (link['request_id'] != operation.request_id or step.input_payload['text'] != result.result_summary):
                    reject('SEALED_EXPRESSION_MISMATCH')
            return choice
        if original.decision_id in self._prepared:
            return self._prepared[original.decision_id]
        steps = []
        for step in original.steps:
            if step.capability not in {'expression.emit', 'contact.send'}:
                steps.append(step)
                continue
            destination = message.preferred_entry_id or message.entry_id
            # A choice is an intention, not authorization to send. Current
            # contact controls are enforced by delivery_current at P17's
            # execute gate (and its final gate). A refusal there is an audited
            # action result; it must not abort unrelated internal Evolution.
            binding = self.service.require_delivery(operation, destination, historical=True)
            device = self.service.devices.get(destination)
            candidates = self.service.routes.get(destination, ())
            if device is None or not candidates:
                reject('SEND_CAPABILITY_MISSING')
            # Availability is a technical signal only. Permission denial above
            # aborts; it never enters the alternative-route loop.
            selected = next((c for c in candidates if self.service.route_available(destination, c) is True), None)
            if selected is None:
                reject('SEND_TECHNICALLY_UNAVAILABLE')
            from continuity_engine.domain.device_operation import DeviceCommand
            command = DeviceCommand('w04-device-v2', selected.split(':', 1)[0].removeprefix('device.'),
                'control:send', result.result_summary, None, None, device.observe(binding.send_use),
                {'request_id': operation.request_id, 'entry_id': destination, 'binding_hash': binding.fingerprint,
                 'item_id': message.item_id or ('matter:' + digest(operation.request_id)[7:]
                                              if result.suggest_future_user_contact else None),
                 'inquiry_id': operation.request_id})
            steps.append(device.step(command, step_id=step.step_id, dependencies=step.dependencies, capability=selected))
        choice = replace(original, steps=tuple(steps))
        self._prepared[original.decision_id] = choice
        return choice
