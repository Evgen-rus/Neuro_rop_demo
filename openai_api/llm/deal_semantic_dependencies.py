"""Semantic-domain to deal-analysis section map used by FULL section repair."""

from __future__ import annotations


DEPENDENCIES: dict[str, set[str]] = {
    "qualification": {"qualification_assessment", "main_risk", "deal_mode", "priority_recommendation", "deal_control_brief", "manager_action_block", "rop_manager_message_block"},
    "commercial_state": {"price_comparability_check", "main_risk", "priority_recommendation", "manager_action_block", "rop_manager_message_block"},
    "payment_state": {"payment_blocker", "money_path_diagnosis", "main_risk", "priority_recommendation", "manager_action_block", "rop_manager_message_block"},
    "money_path": {"money_path_diagnosis", "payment_blocker", "main_risk", "priority_recommendation"},
    "risk_state": {"main_risk", "priority_recommendation", "deal_mode", "resource_control", "manager_action_block", "rop_manager_message_block"},
    "communication_profile": {"client_communication_profile", "objection_handling", "manager_action_block", "rop_manager_message_block", "call_attempt_recommendation"},
}
