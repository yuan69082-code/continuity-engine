"""Target labels do not supply trusted risk metadata."""
from datetime import datetime, timezone
import unittest

from continuity_engine.domain.action import ActionIntent, ActionType, RiskLevel, ResourceLimits, PermissionCheck
from continuity_engine.services.action_service import ActionService


class Granted:
    def check(self, permission, **kwargs):
        return PermissionCheck(permission, True, True, False, False, False, True, 'TEST grant')


class AutonomyRiskTests(unittest.TestCase):
    def assess(self, kind, target, risk=RiskLevel.LOW, confirmed=False):
        intent=ActionIntent('test',kind,'same intent','same evidence',target,'TEST operation',
                            1.0,risk,['test:permit'],0,datetime(2026,9,19,tzinfo=timezone.utc))
        return ActionService(Granted(),None).assess_local_action(intent,subject_id='test',
            environment='TEST',limits=ResourceLimits(),confirmed=confirmed)

    def test_internal_rename_does_not_change_low_risk_or_approval(self):
        for name in ('subject:ordinary','subject:critical','subject:noncritical','C:/noncritical/test'):
            with self.subTest(name=name):
                r=self.assess(ActionType.UPDATE_STATE,name)
                self.assertEqual(r.evaluated_risks.risk_level,RiskLevel.LOW)
                self.assertTrue(r.can_execute_automatically)

    def test_tool_names_cannot_lower_or_raise_trusted_type_minimum(self):
        for name in ('read-only','write','critical-read','noncritical-write'):
            for confirmed in (False,True):
                with self.subTest(name=name,confirmed=confirmed):
                    r=self.assess(ActionType.USE_TOOL,name,confirmed=confirmed)
                    self.assertEqual(r.evaluated_risks.risk_level,RiskLevel.HIGH)
                    self.assertEqual(r.approved,confirmed)

    def test_explicit_high_and_critical_cannot_be_downgraded_by_rename(self):
        for kind in (ActionType.UPDATE_STATE,ActionType.USE_TOOL):
            for risk in (RiskLevel.HIGH,RiskLevel.CRITICAL):
                for name in ('ordinary','noncritical'):
                    r=self.assess(kind,name,risk)
                    self.assertEqual(r.evaluated_risks.risk_level,risk)
                    self.assertFalse(r.can_execute_automatically)
                    self.assertFalse(r.approved)
