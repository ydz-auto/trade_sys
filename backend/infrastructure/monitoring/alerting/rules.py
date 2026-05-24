import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.config.enums import AlertSeverity
from infrastructure.config.defaults.infrastructure.alerting import (
    TRADING_ALERT_RULES,
    SYSTEM_ALERT_RULES,
    PERFORMANCE_ALERT_RULES,
)
from infrastructure.monitoring.alerting.sender import Alert, AlertSender


@dataclass
class AlertRule:
    name: str
    category: str
    condition: str
    severity: AlertSeverity
    message_template: str
    enabled: bool = True
    cooldown_seconds: int = 300
    last_triggered: float = 0

    def can_trigger(self) -> bool:
        if not self.enabled:
            return False

        if self.cooldown_seconds <= 0:
            return True

        return (time.time() - self.last_triggered) >= self.cooldown_seconds

    def mark_triggered(self):
        self.last_triggered = time.time()

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.can_trigger():
            return False

        try:
            return eval(self.condition, {"__builtins__": {}}, context)
        except Exception as e:
            return False

    def format_message(self, context: Dict[str, Any]) -> str:
        message = self.message_template
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        return message


class AlertRuleEngine:
    def __init__(self, alert_sender: Optional[AlertSender] = None):
        self.rules: Dict[str, AlertRule] = {}
        self.alert_sender = alert_sender or AlertSender()
        self._active_alerts: Dict[str, Alert] = {}
        self._on_alert_callback: Optional[Callable] = None

        self._load_default_rules()

    def _load_default_rules(self):
        for rule_config in TRADING_ALERT_RULES + SYSTEM_ALERT_RULES + PERFORMANCE_ALERT_RULES:
            rule = AlertRule(
                name=rule_config["name"],
                category=rule_config["category"],
                condition=rule_config["condition"],
                severity=AlertSeverity(rule_config["severity"]),
                message_template=rule_config["message"],
                enabled=rule_config.get("enabled", True),
            )
            self.rules[rule.name] = rule

    def add_rule(self, rule: AlertRule):
        self.rules[rule.name] = rule

    def remove_rule(self, name: str):
        if name in self.rules:
            del self.rules[name]

    def enable_rule(self, name: str):
        if name in self.rules:
            self.rules[name].enabled = True

    def disable_rule(self, name: str):
        if name in self.rules:
            self.rules[name].enabled = False

    def get_rule(self, name: str) -> Optional[AlertRule]:
        return self.rules.get(name)

    def get_rules_by_category(self, category: str) -> List[AlertRule]:
        return [r for r in self.rules.values() if r.category == category]

    def set_alert_callback(self, callback: Callable):
        self._on_alert_callback = callback

    async def evaluate_all(self, context: Dict[str, Any]) -> List[Alert]:
        triggered_alerts = []

        for rule in self.rules.values():
            if rule.evaluate(context):
                alert = await self._trigger_alert(rule, context)
                if alert:
                    triggered_alerts.append(alert)

        return triggered_alerts

    async def evaluate_rule(self, rule_name: str, context: Dict[str, Any]) -> Optional[Alert]:
        rule = self.rules.get(rule_name)
        if not rule:
            return None

        if rule.evaluate(context):
            return await self._trigger_alert(rule, context)

        return None

    async def _trigger_alert(self, rule: AlertRule, context: Dict[str, Any]) -> Optional[Alert]:
        if not rule.can_trigger():
            return None

        rule.mark_triggered()

        message = rule.format_message(context)

        alert = Alert(
            alert_id=f"alert_{rule.name}_{int(time.time() * 1000)}",
            name=rule.name,
            severity=rule.severity,
            message=message,
            category=rule.category,
            context=context,
        )

        await self.alert_sender.send_alert(alert)

        self._active_alerts[alert.alert_id] = alert

        if self._on_alert_callback:
            try:
                self._on_alert_callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")

        return alert

    def get_active_alerts(self) -> List[Alert]:
        return list(self._active_alerts.values())

    def get_active_alert(self, alert_id: str) -> Optional[Alert]:
        return self._active_alerts.get(alert_id)

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.acknowledged_at = time.time()
            alert.acknowledged_by = acknowledged_by

    async def resolve_alert(self, alert_id: str):
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.status = "RESOLVED"
            alert.resolved_at = time.time()
            del self._active_alerts[alert_id]

    async def resolve_by_name(self, rule_name: str):
        to_resolve = [
            aid for aid, a in self._active_alerts.items() if a.name == rule_name
        ]
        for alert_id in to_resolve:
            await self.resolve_alert(alert_id)

    async def resolve_by_category(self, category: str):
        to_resolve = [
            aid for aid, a in self._active_alerts.items() if a.category == category
        ]
        for alert_id in to_resolve:
            await self.resolve_alert(alert_id)

    async def resolve_all(self):
        for alert_id in list(self._active_alerts.keys()):
            await self.resolve_alert(alert_id)

    def get_alert_stats(self) -> Dict[str, Any]:
        stats = {
            "total_active": len(self._active_alerts),
            "by_severity": {},
            "by_category": {},
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled),
        }

        for alert in self._active_alerts.values():
            severity = alert.severity.value
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            stats["by_category"][alert.category] = stats["by_category"].get(
                alert.category, 0
            ) + 1

        return stats


_default_rule_engine: Optional[AlertRuleEngine] = None


def get_alert_rule_engine(alert_sender: Optional[AlertSender] = None) -> AlertRuleEngine:
    global _default_rule_engine
    if _default_rule_engine is None:
        _default_rule_engine = AlertRuleEngine(alert_sender)
    return _default_rule_engine
