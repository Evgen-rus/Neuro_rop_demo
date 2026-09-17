from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from openai_api.change_detection.decision_engine import INCREMENTAL_LLM_ANALYSIS
from openai_api.llm import analyze_deal_if_changed
from openai_api.llm.incremental_analysis_patch import (
    IMMUTABLE_TOP_LEVEL_FIELDS,
    IncrementalPatchError,
    OUTPUT_KIND_PATCH,
    OUTPUT_KIND_PATCH_NO_CHANGE,
    apply_incremental_analysis_patch,
    merge_incremental_analysis_patch,
    patchable_top_level_blocks,
    validate_incremental_analysis_patch,
)
from openai_api.llm.validation import (
    DEAL_REQUIRED_FIELDS,
    normalize_analysis_for_validation,
    validate_deal_analysis,
)
from storage.rop_db import get_entity_state, merge_deal_daily_quality_state
from test_lead_qualification_assessment import lead_analysis


def audit(*, next_action: int = 0) -> dict:
    reasons = []
    if next_action == 0:
        reasons.append({
            "criterion": "next_action",
            "explanation": "Менеджер оставил инициативу клиенту.",
            "quote": "Как решите, дайте знать.",
        })
    return {
        "status": "assessed",
        "scope_summary": "Учтены звонок с расшифровкой и письмо клиента.",
        "criteria": {
            "next_action": {"score": next_action},
            "value_development": {"score": 1},
            "data_collection": {"score": 1},
        },
        "zero_reasons": reasons,
        "summary_for_rop": "Клиент сравнивает предложения. Менеджеру нужно назначить контрольный звонок.",
        "insufficient_reason": None,
    }


def valid_deal_analysis() -> dict:
    analysis = {key: {} for key in DEAL_REQUIRED_FIELDS}
    lead = lead_analysis()
    for key in ("rop_manager_message_block", "manager_action_block", "qualification_assessment", "main_risk"):
        analysis[key] = deepcopy(lead[key])
    analysis["qualification_assessment"].pop("lead_category", None)
    analysis["qualification_assessment"].pop("lead_route", None)
    analysis.update(
        deal_id="7",
        what_changed=["КП отправлено"],
        communication_quality_audit=audit(next_action=1),
        deal_mode={
            "mode": "active_sale",
            "reason": "Клиент отвечает и есть следующий шаг.",
            "manager_behavior": "Двигать сделку к договору.",
            "rop_focus": "Контролировать срок ответа.",
        },
        deal_control_brief=_control_brief(),
    )
    normalize_analysis_for_validation(analysis)
    validate_deal_analysis(analysis)
    return analysis


def _control_brief(**overrides) -> dict:
    brief = {
        "current_situation": "Клиент получил КП и сравнивает условия.",
        "strengths": ["Есть подтверждённый бюджет."],
        "weaknesses": ["Нет даты решения."],
        "rop_focus": "Подтвердить срок оплаты.",
        "what_to_check_now": "Есть ли дата следующего шага в CRM.",
        "manager_coaching": "Уточни срок решения и внеси его в B24.",
        "known_facts": ["КП отправлено."],
        "missing_facts": ["Дата решения клиента."],
        "contact_goal": "Получить дату решения.",
        "contact_questions": ["Когда примете решение?"],
        "call_script": "Здравствуйте, возвращаюсь к направленному КП.",
        "call_opening_variants": ["Короткое начало один.", "Короткое начало два."],
        "direct_manager_question": "Ты отправил КП и клиент подтвердил получение?",
    }
    brief.update(overrides)
    return brief


def _scoped_audit(*, next_action: int) -> dict:
    value = audit(next_action=next_action)
    value["daily_scope"] = {
        "version": 2,
        "business_date": "2026-08-18",
        "evaluated_through": "2026-08-18T18:00:00+03:00",
        "event_signatures": {"crm_activity:1": "sig"},
        "context_event_ids": ["crm_activity:1"],
    }
    return value


class IncrementalAnalysisPatchTests(unittest.TestCase):
    def test_patchable_blocks_come_from_full_schema_without_deal_id(self) -> None:
        blocks = patchable_top_level_blocks()
        self.assertTrue(DEAL_REQUIRED_FIELDS - {"deal_id"} <= blocks)
        self.assertNotIn("deal_id", blocks)
        self.assertEqual(IMMUTABLE_TOP_LEVEL_FIELDS, frozenset({"deal_id"}))
        self.assertIn("recommendation_feedback", blocks)
        self.assertIn("communication_quality_audit", blocks)
        self.assertIn("what_changed", blocks)

    def test_single_changed_block_replaces_only_that_top_level(self) -> None:
        previous = valid_deal_analysis()
        snapshot = deepcopy(previous)
        new_risk = {
            "risk_level": "high",
            "risk_type": "silence",
            "description": "Клиент перестал отвечать после КП.",
        }
        merged, kind = apply_incremental_analysis_patch(
            previous,
            {"no_change": False, "updates": {"main_risk": new_risk}},
        )
        self.assertEqual(kind, OUTPUT_KIND_PATCH)
        self.assertEqual(merged["main_risk"], new_risk)
        self.assertEqual(merged["deal_mode"], snapshot["deal_mode"])
        self.assertEqual(merged["deal_control_brief"], snapshot["deal_control_brief"])
        self.assertEqual(previous, snapshot)
        validate_deal_analysis(deepcopy(merged))
        self.assertNotIn("updates", merged)
        self.assertNotIn("no_change", merged)

    def test_several_blocks_replace_wholly_and_keep_the_rest(self) -> None:
        previous = valid_deal_analysis()
        snapshot = deepcopy(previous)
        new_brief = _control_brief(rop_focus="Проверить паузу клиента.")
        new_risk = {
            "risk_level": "medium_high",
            "risk_type": "pause",
            "description": "Клиент взял паузу без даты.",
        }
        new_audit = audit(next_action=0)
        merged, kind = apply_incremental_analysis_patch(
            previous,
            {
                "no_change": False,
                "updates": {
                    "deal_control_brief": new_brief,
                    "main_risk": new_risk,
                    "communication_quality_audit": new_audit,
                },
            },
        )
        self.assertEqual(kind, OUTPUT_KIND_PATCH)
        self.assertEqual(merged["deal_control_brief"], new_brief)
        self.assertEqual(merged["main_risk"], new_risk)
        self.assertEqual(merged["communication_quality_audit"], new_audit)
        self.assertEqual(merged["deal_mode"], snapshot["deal_mode"])
        self.assertEqual(merged["qualification_assessment"], snapshot["qualification_assessment"])
        validate_deal_analysis(deepcopy(merged))

    def test_no_change_keeps_previous_analysis_and_skips_full_rebuild(self) -> None:
        previous = valid_deal_analysis()
        snapshot = deepcopy(previous)
        merged, kind = apply_incremental_analysis_patch(
            previous,
            {"no_change": True, "updates": {}},
        )
        self.assertEqual(kind, OUTPUT_KIND_PATCH_NO_CHANGE)
        self.assertEqual(merged, snapshot)
        self.assertEqual(previous, snapshot)
        self.assertIsNot(merged, previous)

    def test_no_change_rejects_non_empty_updates(self) -> None:
        with self.assertRaisesRegex(IncrementalPatchError, "empty updates"):
            validate_incremental_analysis_patch(
                {"no_change": True, "updates": {"main_risk": {"risk_level": "low"}}}
            )

    def test_unknown_block_is_rejected_before_merge(self) -> None:
        previous = valid_deal_analysis()
        snapshot = deepcopy(previous)
        with self.assertRaisesRegex(IncrementalPatchError, "forbidden block"):
            apply_incremental_analysis_patch(
                previous,
                {"no_change": False, "updates": {"invented_field": {}}},
            )
        self.assertEqual(previous, snapshot)

    def test_deal_id_cannot_be_patched(self) -> None:
        previous = valid_deal_analysis()
        with self.assertRaisesRegex(IncrementalPatchError, "forbidden block"):
            apply_incremental_analysis_patch(
                previous,
                {"no_change": False, "updates": {"deal_id": "999"}},
            )

    def test_full_analysis_payload_is_rejected_as_patch(self) -> None:
        previous = valid_deal_analysis()
        with self.assertRaises(IncrementalPatchError):
            apply_incremental_analysis_patch(previous, previous)

    def test_damaged_block_fails_full_validation(self) -> None:
        previous = valid_deal_analysis()
        with self.assertRaisesRegex(IncrementalPatchError, "FULL validation"):
            apply_incremental_analysis_patch(
                previous,
                {
                    "no_change": False,
                    "updates": {
                        "main_risk": {"risk_level": "medium"},
                        "deal_control_brief": {"current_situation": "обрезанный блок"},
                    },
                },
            )

    def test_incompatible_baseline_cannot_be_merged(self) -> None:
        with self.assertRaisesRegex(IncrementalPatchError, "must be an object"):
            merge_incremental_analysis_patch(
                None,
                {"no_change": True, "updates": {}},
            )

    def test_daily_quality_keeps_earned_score_after_weaker_patch(self) -> None:
        previous = valid_deal_analysis()
        previous["communication_quality_audit"] = _scoped_audit(next_action=1)
        weaker = _scoped_audit(next_action=0)
        merged, _kind = apply_incremental_analysis_patch(
            previous,
            {"no_change": False, "updates": {"communication_quality_audit": weaker}},
        )
        self.assertEqual(merged["communication_quality_audit"]["criteria"]["next_action"]["score"], 0)
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "state.sqlite"
            merge_deal_daily_quality_state(
                db_path, deal_id="7", audit=previous["communication_quality_audit"],
            )
            saved = merge_deal_daily_quality_state(
                db_path, deal_id="7", audit=merged["communication_quality_audit"],
            )
        self.assertEqual(saved["audit"]["criteria"]["next_action"]["score"], 1)
        self.assertEqual(saved["audit"]["criteria"]["value_development"]["score"], 1)

    def test_persisted_analysis_is_full_json_not_patch(self) -> None:
        previous = valid_deal_analysis()
        merged, kind = apply_incremental_analysis_patch(
            previous,
            {
                "no_change": False,
                "updates": {
                    "main_risk": {
                        "risk_level": "high",
                        "risk_type": "silence",
                        "description": "Клиент молчит.",
                    }
                },
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "state.sqlite"
            analysis_path = root / "analysis.json"
            payload = {
                "analysis_mode": "incremental",
                "analysis_output_kind": kind,
                "evidence_ids_included": [],
                "analysis": merged,
            }
            analysis_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            run_id = analyze_deal_if_changed.persist_successful_llm_run(
                db_path=db_path,
                args=SimpleNamespace(deal_id="7", deal_root=str(root), model=None),
                fingerprint="fp",
                snapshot={},
                decision_status=INCREMENTAL_LLM_ANALYSIS,
                paths={"analysis": analysis_path, "report": root / "report.md", "raw": root / "raw.txt"},
                decision_reason={"status": INCREMENTAL_LLM_ANALYSIS},
                evidence_coverage={},
                canonical_state={
                    "schema_id": "canonical_bitrix_state",
                    "schema_version": "1",
                    "owner": {"entity_type": "deal", "entity_id": "7"},
                    "semantic_fingerprint": "canonical-fp",
                },
                available_evidence=[],
            )
            saved = json.loads(analysis_path.read_text(encoding="utf-8"))
            state = get_entity_state(db_path, "deal", "7")
        self.assertEqual(run_id, saved["analysis_run_id"])
        self.assertNotIn("updates", saved)
        self.assertNotIn("updates", saved["analysis"])
        self.assertEqual(saved["analysis"]["main_risk"]["risk_level"], "high")
        self.assertEqual(saved["analysis"]["deal_id"], "7")
        self.assertEqual(saved["analysis_output_kind"], OUTPUT_KIND_PATCH)
        self.assertEqual(state["last_analysis"]["analysis"]["main_risk"]["risk_level"], "high")
        self.assertEqual(state["last_analysis_status"], INCREMENTAL_LLM_ANALYSIS)

    def test_what_changed_must_be_a_list(self) -> None:
        with self.assertRaisesRegex(IncrementalPatchError, "must be a list"):
            validate_incremental_analysis_patch(
                {"no_change": False, "updates": {"what_changed": {"item": "нет"}}}
            )


if __name__ == "__main__":
    unittest.main()
