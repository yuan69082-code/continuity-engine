"""Deterministic internal dynamics and deliberation, with no persistence rights."""
from copy import deepcopy
from dataclasses import replace
import math

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.dynamic_mind import (
    DRIVES, MindState, MindEvolution, MindValidationError, timestamp, utc, text, ratio,
)


def bounded(value):
    return round(min(1.0, max(0.0, value)), 9)


class MindDynamics:
    """Rates govern continuous need accumulation, not speech or moral policy.

    Internal alternatives are considered against competing needs and commitments.
    No emotion threshold maps to a line of dialogue or a reality permission.
    """
    def __init__(self, *, need_hours=None):
        self.need_hours = need_hours or dict(zip(DRIVES, (6, 3, 12, 5, 4, 8, 6)))
        if set(self.need_hours) != set(DRIVES) or any(
                type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                for v in self.need_hours.values()):
            raise MindValidationError('MIND_RATE_POLICY_INVALID')

    def advance(self, state, *, at, appraisals=(), regulation=None, resolutions=(), outcomes=()):
        state = MindState.from_dict(state.to_dict())
        at = utc(at)
        if at < state.updated_at:
            raise MindValidationError('MIND_CLOCK_REGRESSION')
        elapsed = (at - state.updated_at).total_seconds()
        normalized = []
        known = {key for episode in state.episodes for key in episode['source_keys']}
        for appraisal in appraisals:
            required = {'source_key', 'object', 'kind', 'interpretation', 'unresolved', 'intensity'}
            if not isinstance(appraisal, dict) or set(appraisal) not in (required, required | {'occurred_at'}):
                raise MindValidationError('MIND_APPRAISAL_SHAPE_INVALID')
            if 'occurred_at' in appraisal and utc(appraisal['occurred_at']) > at:
                raise MindValidationError('MIND_APPRAISAL_TIME_INVALID')
            if appraisal['source_key'] not in known:
                normalized.append(appraisal)
                known.add(appraisal['source_key'])
        appraisals = normalized
        if not elapsed and not appraisals and regulation is None and not resolutions and not outcomes:
            return MindEvolution(state, self.influence(state), ())
        now = timestamp(at)
        hours = elapsed / 3600
        changes = []
        episodes = deepcopy(state.episodes)
        for appraisal in appraisals:
            required = {'source_key', 'object', 'kind', 'interpretation', 'unresolved', 'intensity'}
            if not isinstance(appraisal, dict) or set(appraisal) not in (required, required | {'occurred_at'}):
                raise MindValidationError('MIND_APPRAISAL_SHAPE_INVALID')
            for key in ('source_key', 'object', 'kind', 'interpretation', 'unresolved'):
                text(appraisal[key])
            ratio(appraisal['intensity'])
            if any(appraisal['source_key'] in e['source_keys'] for e in episodes):
                continue  # Same root observation is not a second emotional event.
            key = 'episode:' + digest([appraisal['object'], appraisal['kind']])[7:]
            episode = next((e for e in episodes if e['id'] == key), None)
            if episode is None:
                episode = dict(id=key, object=appraisal['object'], kind=appraisal['kind'],
                               source_keys=[], interpretation=appraisal['interpretation'],
                               unresolved=appraisal['unresolved'], status='unresolved',
                               intensity=0.0, created_at=now, updated_at=now, trajectory=[], resolution=None)
                episodes.append(episode)
            episode['source_keys'].append(appraisal['source_key'])
            # Keep the latest objective experienced root, independently of
            # appraisal/processing time and the bounded display trajectory.
            # Legacy internal appraisals without occurrence retain their shape.
            if 'occurred_at' in appraisal:
                previous_basis = episode.get('concern_basis')
                if previous_basis is None or utc(appraisal['occurred_at']) > utc(previous_basis['occurred_at']):
                    episode['concern_basis'] = {'source_key': appraisal['source_key'],
                                               'occurred_at': timestamp(appraisal['occurred_at'])}
            episode.update(intensity=bounded(episode['intensity'] +
                                             (1 - episode['intensity']) * appraisal['intensity']),
                           interpretation=appraisal['interpretation'], updated_at=now,
                           status='unresolved', resolution=None, unresolved=appraisal['unresolved'])
            episode['trajectory'] = (episode['trajectory'] + [{'at': now, 'reason': 'appraised-source',
                                      'source_key': appraisal['source_key']}])[-8:]
            changes.append('EPISODE_APPRAISED:' + key)
        for resolution in resolutions:
            if set(resolution) != {'episode_id', 'interpretation', 'reason', 'source_keys', 'resolve'}:
                raise MindValidationError('MIND_RESOLUTION_SHAPE_INVALID')
            episode = next((e for e in episodes if e['id'] == resolution['episode_id']), None)
            if episode is None or not resolution['source_keys']:
                raise MindValidationError('MIND_RESOLUTION_BASIS_MISSING')
            if not set(resolution['source_keys']) <= set(episode['source_keys']):
                raise MindValidationError('MIND_RESOLUTION_UNBOUND')
            text(resolution['reason']); text(resolution['interpretation'])
            # This is an internal proposal. Service/Thinking/Evolution must commit it.
            episode.update(status='resolved' if resolution['resolve'] else 'processing',
                           interpretation=resolution['interpretation'], resolution=deepcopy(resolution), updated_at=now)
            changes.append('EPISODE_COGNITIVE_RESOLUTION:' + episode['id'])
        pressure = sum(e['intensity'] for e in episodes if e['status'] != 'resolved')
        fatigue = bounded(state.fatigue + (1 - state.fatigue) * (1 - math.exp(-hours / 16)))
        tension = bounded(state.somatic['tension'] * math.exp(-hours / 12) +
                          (1 - math.exp(-pressure / 4)) * (1 - state.somatic['tension']))
        arousal = bounded((state.arousal + tension + state.somatic['restlessness'] +
                           state.somatic['excitement'] + pressure / (1 + pressure)) / 5)
        somatic = {**state.somatic, 'tension': tension, 'heaviness': fatigue,
                   'relaxation': bounded(1 - (tension + fatigue) / 2)}
        drives = {d: bounded(1 - (1 - state.drives[d]) * math.exp(-hours / self.need_hours[d])) for d in DRIVES}
        drives['rest'] = bounded(drives['rest'] + fatigue * hours / (8 + hours))
        drives['protection'] = bounded(drives['protection'] + tension * hours / (8 + hours))
        drives['sexual'] = bounded(drives['sexual'] +
                                   (somatic['warmth'] + somatic['excitement']) * hours / (24 + hours))
        conflicts = self._conflicts(state.dispositions, episodes)
        desires = deepcopy(state.desires)
        for drive in DRIVES:
            matching = [d for d in desires if d['drive'] == drive and d['object'] == 'self']
            if not matching and drives[drive] > 0:
                identity = 'desire:' + drive
                if any(d['id'] == identity for d in desires):
                    identity += ':' + digest([now, sorted(d['id'] for d in desires)])[7:23]
                desired = dict(id=identity, drive=drive, object='self', origin='ENDOGENOUS',
                               phase='arise', strength=drives[drive], reason='elapsed need: ' + drive,
                               created_at=now, updated_at=now, trajectory=[])
                desires.append(desired)
                matching.append(desired)
            # Transform preserves identity. Multiple desires for one drive
            # remain distinct and all receive the same elapsed opportunity.
            for desired in matching:
                previous = desired['strength']
                if desired['phase'] in {'disappear', 'abandon', 'act'}:
                    phase = 'recur' if drives[drive] > previous and elapsed > 0 else desired['phase']
                elif desired['created_at'] == now:
                    phase = 'arise'
                else:
                    phase = 'intensify' if drives[drive] > previous else 'weaken' if drives[drive] < previous else 'persist'
                desired.update(phase=phase, strength=drives[drive], updated_at=now)
                desired['trajectory'] = (desired['trajectory'] + [{'at': now, 'phase': phase,
                                           'reason': 'elapsed/body/need integration'}])[-8:]
        reg = deepcopy(state.regulation)
        if regulation is not None:
            if set(regulation) != {'strategy', 'desire_id', 'reason'} or regulation['strategy'] not in {'suppress', 'reappraise', 'rest'}:
                raise MindValidationError('MIND_REGULATION_INTENT_INVALID')
            desired = next((d for d in desires if d['id'] == regulation['desire_id']), None)
            if desired is None:
                raise MindValidationError('MIND_REGULATION_DESIRE_MISSING')
            text(regulation['reason'])
            capacity = bounded((1 - fatigue) * (1 - arousal) * (0.5 + somatic['relaxation'] / 2))
            load = bounded((desired['strength'] + tension + pressure / (1 + pressure)) / 3)
            success = capacity >= load
            reg = {**regulation, 'outcome': 'success' if success else 'failure', 'capacity': capacity, 'load': load}
            desired.update(phase='suppress' if success else 'fail_to_suppress',
                           strength=bounded(desired['strength'] * (1 - capacity)) if success else desired['strength'])
            drives[desired['drive']] = desired['strength']
            desired['trajectory'] = (desired['trajectory'] + [{'at': now, 'phase': desired['phase'],
                                                               'reason': regulation['reason']}])[-8:]
            if success and regulation['strategy'] == 'rest':
                fatigue = bounded(fatigue * (1 - capacity))
            changes.append('REGULATION_' + reg['outcome'].upper())
        for outcome in outcomes:
            expected = {'desire_id', 'phase', 'reason'} | ({'new_drive'} if outcome.get('phase') == 'transform' else set())
            if set(outcome) != expected or outcome['phase'] not in {
                    'weaken', 'persist', 'disappear', 'conflict', 'transform', 'act', 'abandon'}:
                raise MindValidationError('MIND_DESIRE_OUTCOME_INVALID')
            desired = next((d for d in desires if d['id'] == outcome['desire_id']), None)
            if desired is None:
                raise MindValidationError('MIND_DESIRE_OUTCOME_UNBOUND')
            text(outcome['reason'])
            desired.update(phase=outcome['phase'], reason=outcome['reason'], updated_at=now)
            if outcome['phase'] == 'weaken':
                desired['strength'] = bounded(desired['strength'] / 2)
                drives[desired['drive']] = desired['strength']
            if outcome['phase'] == 'transform':
                if outcome['new_drive'] not in DRIVES or outcome['new_drive'] == desired['drive']:
                    raise MindValidationError('MIND_DESIRE_TRANSFORMATION_INVALID')
                desired['drive'] = outcome['new_drive']
            if outcome['phase'] in {'act', 'disappear', 'abandon'}:
                desired['strength'] = 0.0
                drives[desired['drive']] = 0.0
            desired['trajectory'] = (desired['trajectory'] + [{'at': now, 'phase': desired['phase'],
                                                               'reason': outcome['reason']}])[-8:]
        will = self.deliberate(desires, conflicts, fatigue, episodes)
        thoughts = deepcopy(state.thoughts)
        for thought in thoughts:
            thought['conflict_ids'] = [c['id'] for c in conflicts]
            linked = [d for d in desires if d['id'] in thought['desire_ids']]
            thought['unresolved'] = any(d['phase'] not in {'disappear', 'abandon', 'act', 'suppress'} for d in linked)
        for desire in desires:
            if desire['phase'] in {'disappear', 'abandon', 'act', 'suppress'}:
                continue
            key = 'thought:' + desire['id']
            thought = next((t for t in thoughts if t['id'] == key), None)
            concern = next((e for e in episodes if e['status'] != 'resolved'), None)
            theme = concern['object'] if concern else desire['drive']
            if thought is None:
                thoughts.append(dict(id=key, theme=theme,
                    content='I keep considering ' + theme + ' in relation to my need for ' + desire['drive'] + '.',
                    reason='Engine deliberation retains an unresolved internal concern.',
                    desire_ids=[desire['id']], conflict_ids=[c['id'] for c in conflicts],
                    created_at=now, last_recurred_at=now, recurrences=1, unresolved=True))
            elif elapsed > 0:
                thought.update(last_recurred_at=now, recurrences=thought['recurrences'] + 1,
                    theme=theme, content='I keep considering ' + theme + ' in relation to my need for ' + desire['drive'] + '.',
                    unresolved=True)
        occupancy = len([t for t in thoughts if t['unresolved']])
        # Trapezoidal local experience integral depends on coupled state, not a constant multiplier.
        experience = 1 + (state.fatigue + fatigue) / 4 + tension * occupancy / (8 + occupancy) + arousal / 3
        proposed = replace(state, updated_at=at, drives=drives, fatigue=fatigue, arousal=arousal,
                           somatic=somatic, episodes=episodes, desires=desires, conflicts=conflicts,
                           will=will, thoughts=thoughts, regulation=reg,
                           subjective_seconds=round(state.subjective_seconds + elapsed * experience, 6))
        return MindEvolution(proposed, self.influence(proposed), tuple(changes))

    @staticmethod
    def _conflicts(dispositions, episodes):
        by_object = {}
        for value in dispositions:
            by_object.setdefault(value['object'], set()).add(value['kind'])
        for value in episodes:
            if value['status'] != 'resolved':
                by_object.setdefault(value['object'], set()).add(value['kind'].upper())
        result = []
        for obj, poles in sorted(by_object.items()):
            for a, b in [('LOVE', 'HATE'), ('LOVE', 'ANGER'), ('APPROACH', 'AVOID'), ('TRUST', 'DOUBT')]:
                if {a, b} <= poles:
                    result.append(dict(id='conflict:' + digest([obj, a, b])[7:], object=obj,
                        poles=[a, b], reason='Both appraisals remain meaningful to the subject; neither is a factual winner.'))
        return result

    @staticmethod
    def deliberate(desires, conflicts, fatigue, episodes):
        result = []
        unresolved = [e for e in episodes if e['status'] != 'resolved']
        for desire in desires:
            supporting = ['felt need for ' + desire['drive'], desire['reason']]
            supporting = list(dict.fromkeys(supporting))
            opposing = []
            if conflicts:
                opposing.append('simultaneous incompatible approaches remain unresolved')
            if fatigue > 1 - fatigue and desire['drive'] != 'rest':
                opposing.append('continuing now competes with recovery of attention')
            if unresolved:
                opposing.append('the meaning of a prior emotional episode is still unsettled')
            terminal = desire['phase'] in {'disappear', 'abandon', 'act'}
            stance = 'abandon' if terminal else 'hold' if opposing else 'pursue'
            decision = 'DEFER' if terminal else 'QUESTION' if conflicts or unresolved else 'DEFER' if opposing else 'PURSUE'
            tendency = ('rest' if desire['drive'] == 'rest' else 'seek-understanding' if conflicts or unresolved
                        else 'wait' if opposing else desire['drive'])
            result.append(dict(desire_id=desire['id'], stance=stance,
                supporting_reasons=supporting, opposing_reasons=opposing,
                alternatives=['reconsider after new understanding', 'continue without resolving the conflict', 'defer'],
                commitment='Keep this desire distinct from deciding to perform a reality action.',
                decision=decision, action_tendency=tendency))
        return result

    @staticmethod
    def influence(state):
        active = [e for e in state.episodes if e['status'] != 'resolved']
        themes = list(dict.fromkeys([e['object'] for e in active] +
                                   [t['theme'] for t in state.thoughts if t['unresolved']]))
        waiting_load = 1 - math.exp(-state.subjective_seconds / (3600 * (1 + len(state.thoughts))))
        narrowing = bounded((state.fatigue + state.arousal + state.somatic['tension'] + waiting_load) / 4)
        breadth = max(1, round(8 * (1 - narrowing)))
        return {'attention': {'breadth': breadth, 'narrowing': narrowing, 'themes': themes[:breadth]},
                'interpretations': [e['interpretation'] for e in active[:breadth]],
                'action_tendencies': list(dict.fromkeys(w['action_tendency'] for w in state.will)),
                'decisions': list(dict.fromkeys(w['decision'] for w in state.will)),
                'subjective_seconds': state.subjective_seconds,
                'regulation': state.regulation.get('outcome', 'not-attempted'),
                'not_factual_evidence': True}


class MindCognition:
    """P14 integration on the original C1 input and Thinking/Evolution path.

    It reads one authorized current SubjectState. It neither saves that state
    nor allocates resources, wakes a subject, dispatches an action, or calls a
    provider. The returned mutation is still only a proposal to Action Gate.
    """
    def __init__(self, core, dynamics=None):
        self.core = core
        self.dynamics = dynamics or MindDynamics()

    def capture(self, perception, operation):
        from continuity_engine.domain.context_routing import (
            ContextRoutingRequest, ContextPartition, ContextCandidateReference,
        )
        from continuity_engine.domain.dynamic_mind import context_state_document
        from .context_router_service import _canonical_hash as source_hash
        c = self.core
        if (perception.subject_id, operation.subject_id) != (c.subject_id, c.subject_id):
            raise MindValidationError('MIND_SUBJECT_BOUNDARY_INVALID')
        request = ContextRoutingRequest(operation.request_id, perception.perception_id, c.subject_id,
            c.environment, perception.source_revision, perception.perceived_at, ('internal_drive',), c.retrieval_budget)
        if not c.permission.authorize_source(request, 'engine.subject-state', ContextPartition.SUBJECT_STATE).allowed:
            raise MindValidationError('MIND_SOURCE_PERMISSION_DENIED')
        current = c.subject_states.load(c.subject_id)
        if current.revision != perception.source_revision:
            raise MindValidationError('MIND_SOURCE_REVISION_CHANGED')
        reference = ContextCandidateReference('engine.subject-state', ContextPartition.SUBJECT_STATE,
            current.subject_id + ':intentions', current.subject_id, c.environment,
            'revision:' + str(current.revision), source_hash(context_state_document(current)['intentions']),
            'SUBJECT_STATE_PARTITION', 1, 1.0, current.temporal.updated_at, ('P14_CURRENT_MIND_BASIS',))
        if not c.permission.authorize_reference(request, reference).allowed:
            raise MindValidationError('MIND_REFERENCE_PERMISSION_DENIED')
        previous = current.intentions.dynamic_mind
        state = (MindState.from_dict(previous) if previous is not None else
                 MindState.create(c.subject_id, c.environment, current.temporal.created_at))
        if state.environment != c.environment:
            raise MindValidationError('MIND_ENVIRONMENT_BOUNDARY_INVALID')
        frame = self.dynamics.advance(state, at=perception.perceived_at)
        return {'version': 'p14-cognition-input-v1', 'reference': reference.to_dict(),
                'source_revision': current.revision, 'before_hash': digest(previous),
                'base': state.to_dict(), 'appraisal_sources': [],
                'proposal': frame.state.to_dict(), 'influence': frame.influence,
                'change_reasons': list(frame.changes), 'authority': 'UNCOMMITTED_INTERNAL_CANDIDATE'}

    def finalize(self, captured, composition):
        """Only actual exact Composer material can supply a new experienced root.

        The local structured experience vocabulary is an Engine semantic port,
        not a provider response or an externally approved StateMutation. Free
        natural-language understanding remains a replaceable Thinking capability.
        """
        import json
        from continuity_engine.domain.context_composition import ContextAuthority
        mapping = {'boundary_crossed': 'anger', 'unexpected_loss': 'sadness', 'threat': 'fear',
                   'contamination': 'disgust', 'stagnation': 'boredom', 'support_received': 'joy',
                   'unexpected_support': 'delight', 'blocked_agency': 'helplessness', 'apology_offered': 'joy',
                   'expectation_met': 'joy'}
        appraisals = []
        corroboration = {}
        for fragment in composition.snapshot.fragments:
            raw = fragment.source_id == 'engine.timeline' and fragment.authority is ContextAuthority.RAW_SOURCE
            memory = fragment.source_id == 'engine.memory' and fragment.authority is ContextAuthority.CONFIRMED_MEMORY
            if not (raw or memory) or fragment.missing_markers or fragment.conflict_markers:
                continue
            # A single experienced root can be recalled as Memory, but never
            # counted again as an independent Timeline experience. Summaries and
            # multi-root paraphrases cannot manufacture a new emotional root.
            roots = [r for r in fragment.provenance_roots if r.startswith('event:')]
            if memory and len(roots) != 1:
                continue
            body = fragment.content
            if memory:
                if not body.startswith('interaction: '):
                    continue
                body = body[len('interaction: '):]
            try:
                content = json.loads(body)
            except (ValueError, TypeError):
                continue
            if not isinstance(content, dict) or set(content) != {'experienced'}:
                continue
            fact = content['experienced']
            if not isinstance(fact, dict) or set(fact) != {'object', 'observation', 'expectation', 'consequence', 'impact'}:
                raise MindValidationError('MIND_EXPERIENCED_SOURCE_SHAPE_INVALID')
            if fact['observation'] not in mapping:
                raise MindValidationError('MIND_EXPERIENCED_SOURCE_KIND_INVALID')
            text(fact['object']); text(fact['expectation']); text(fact['consequence']); ratio(fact['impact'])
            root = roots[0] if memory else 'event:' + fragment.stable_source_id
            # The root identity, not a changed rendering/hash, defines an
            # independent experience. Exact versions stay bound in C1 input.
            source_key = root
            if fact['observation'] == 'expectation_met':
                group = corroboration.setdefault((fact['object'], fact['expectation']), {})
                previous = group.get(source_key, (fragment.confidence, fragment.occurred_at))
                # RAW and Memory are one root, never two votes; retain the
                # conservative consumption confidence and objective time.
                group[source_key] = (min(previous[0], fragment.confidence),
                                     min(previous[1], fragment.occurred_at))
            appraisals.append({'source_key': source_key,
                'occurred_at': timestamp(fragment.occurred_at),
                'object': fact['object'], 'kind': mapping[fact['observation']],
                'interpretation': fact['consequence'] + ' in relation to ' + fact['expectation'],
                'unresolved': 'Whether subsequent experience changes this understanding of ' + fact['object'],
                'intensity': fact['impact'] * fragment.confidence})
        base = MindState.from_dict(captured['base'])
        at = utc(captured['proposal']['updated_at'])
        # A duplicated RAW/Memory root must not acquire a different strength
        # merely because Composer presents one rendering first.
        appraisals.sort(key=lambda a: (a['intensity'], utc(a['occurred_at']), a['source_key']))
        by_root = {}
        for appraisal in appraisals:
            by_root.setdefault(appraisal['source_key'], appraisal)
        appraisals = sorted(by_root.values(), key=lambda a: (utc(a['occurred_at']), a['source_key']))
        frame = self.dynamics.advance(base, at=at, appraisals=appraisals)
        # Understanding compares the still-present negative interpretation with
        # current, independently identified experience. An apology is excluded.
        # This is a cognitive candidate, not a truth claim or a state write.
        resolutions = []
        episodes = deepcopy(frame.state.episodes)
        for episode in episodes:
            expectation = episode['interpretation'].rsplit(' in relation to ', 1)[-1]
            support = corroboration.get((episode['object'], expectation), {})
            # A currently readable old repair does not resolve a later harm.
            # Legacy records have no objective basis: conservatively use the
            # latest appraisal time, never infer missing chronology from text.
            basis = episode.get('concern_basis')
            concern_at = (utc(basis['occurred_at']) if basis else
                          max((utc(p['at']) for p in episode['trajectory']), default=utc(episode['updated_at'])))
            support = {key: confidence for key, (confidence, occurred_at) in support.items()
                       if occurred_at > concern_at}
            supporting = sorted(support)
            if episode['kind'] not in {'anger', 'fear', 'sadness', 'helplessness'} or not supporting:
                continue
            if episode['status'] == 'resolved':
                continue
            for key in supporting:
                if key not in episode['source_keys']:
                    episode['source_keys'].append(key)
            resolutions.append({'episode_id': episode['id'],
                'interpretation': 'Current experience of ' + episode['object'] +
                    ' is consistent with the previously unmet expectation; retain the original experience in relation to ' + expectation,
                'reason': 'Compare the unresolved expectation with ' + str(len(supporting)) +
                    ' independently identified, currently composed instances after concern ' +
                    (basis['source_key'] if basis else 'legacy appraisal') + ' at ' + timestamp(concern_at) +
                    '; one instance leaves uncertainty.',
                'source_keys': supporting,
                'resolve': len(supporting) >= 2 and sum(support.values()) >= episode['intensity']})
        if resolutions:
            understood = self.dynamics.advance(replace(frame.state, episodes=episodes), at=at, resolutions=resolutions)
            frame = MindEvolution(understood.state, understood.influence, frame.changes + understood.changes)
        # Repeated unresolved concern forms an internal regulation intent. The
        # attempt may fail; no platform permission gate can erase this concern.
        recurring = any(t['unresolved'] and t['recurrences'] > 1 for t in frame.state.thoughts)
        unsettled = any(e['status'] != 'resolved' for e in frame.state.episodes)
        if recurring and unsettled and at > base.updated_at:
            target = next((d for d in frame.state.desires if d['drive'] == 'protection'), None)
            if target is not None:
                regulated = self.dynamics.advance(frame.state, at=at, regulation={
                    'strategy': 'reappraise', 'desire_id': target['id'],
                    'reason': 'Recurring unresolved concern competes with attention; attempt to contain its demand.'})
                frame = MindEvolution(regulated.state, regulated.influence, frame.changes + regulated.changes)
        return {**captured, 'proposal': frame.state.to_dict(), 'influence': frame.influence,
                'appraisal_sources': [a['source_key'] for a in appraisals], 'change_reasons': list(frame.changes)}

    def current(self, context):
        from continuity_engine.domain.context_routing import ContextCandidateReference
        from continuity_engine.domain.dynamic_mind import context_state_document
        from .context_router_service import _canonical_hash as source_hash
        c = self.core
        m = context.mind
        if m is None:
            return False
        reference = ContextCandidateReference.from_dict(m['reference'])
        request = context.route.plan.request
        if not c.permission.authorize_source(request, reference.source_id, reference.partition).allowed:
            return False
        if not c.permission.authorize_reference(request, reference).allowed:
            return False
        state = c.subject_states.load(c.subject_id)
        if (reference.subject_id != c.subject_id or reference.environment != c.environment
                or state.revision != m['source_revision']
                or digest(state.intentions.dynamic_mind) != m['before_hash']
                or source_hash(context_state_document(state)['intentions']) != reference.content_hash):
            return False
        # A private pre-route read is not permission to bypass Composer's range.
        composed = any(f.source_id == reference.source_id and f.stable_source_id == reference.stable_id
                   and f.version == reference.version and f.content_hash == reference.content_hash
                   for f in context.composition.snapshot.fragments)
        if not composed:
            return False
        from types import SimpleNamespace
        rebuilt = self.capture(SimpleNamespace(subject_id=request.subject_id,
            source_revision=request.source_revision, perception_id=request.perception_id,
            perceived_at=request.routed_at), SimpleNamespace(subject_id=request.subject_id, request_id=request.request_id))
        return self.finalize(rebuilt, context.composition) == m

    def process(self, perception, result):
        from continuity_engine.domain.events import StateMutation, ChangeOperation
        context = perception.continuity_context
        if context is None or context.mind is None or not self.core.current(context):
            raise MindValidationError('MIND_CONTEXT_NO_LONGER_CURRENT')
        m = context.mind
        proposed = MindState.from_dict(m['proposal'])
        if proposed.subject_id != perception.subject_id or proposed.updated_at != perception.perceived_at:
            raise MindValidationError('MIND_PROPOSAL_BINDING_INVALID')
        mutations = list(result.proposed_mutations)
        if any(p.field_path == 'intentions.dynamic_mind' for p in mutations):
            raise MindValidationError('MIND_PROVIDER_CANNOT_SUPPLY_INTERNAL_STATE')
        if digest(proposed.to_dict()) != m['before_hash']:
            mutations.append(StateMutation('intentions.dynamic_mind', ChangeOperation.SET,
                proposed.to_dict(), 'Internal continuous cognition; original source revision and C1 input bound.'))
        decisions = m['influence']['decisions']
        # Decide on unsettled meaning and competing commitments, before any
        # expression is produced. No generated sentence is used as state evidence.
        mode = ('QUESTION' if 'QUESTION' in decisions else 'DEFER' if 'DEFER' in decisions
                else 'PURSUE' if 'PURSUE' in decisions else result.expression_mode)
        # A felt drive is not a mandate to override a considered subject choice.
        # Explicit Thinking stances (including refusal and silence) remain valid
        # alternatives to pursuing a desire. All still pass the original gates.
        if result.expression_mode not in {None, 'RESPOND'}:
            mode = result.expression_mode
        return replace(result, update_subject_state=bool(mutations), proposed_mutations=mutations,
                       expression_mode=mode,
                       request_more_memory=(result.request_more_memory or 'QUESTION' in decisions),
                       additional_memory_query=(result.additional_memory_query or
                           (' '.join(m['influence']['attention']['themes']) or 'unresolved continuity')
                           if result.request_more_memory or 'QUESTION' in decisions else None),
                       should_wait=(result.should_wait or mode == 'DEFER'),
                       rationale_summary=result.rationale_summary +
                       ' Engine deliberation basis: ' + digest(proposed.will) +
                       '; cognition input: ' + context.binding_hash())
