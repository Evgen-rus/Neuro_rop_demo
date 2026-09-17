from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from openai_api.llm.analyze_deal import (
    COMPATIBLE_DEAL_PROMPT_VERSIONS,
    DEAL_ID_SECTION_MARKER,
    DEAL_PROMPT_CACHE_KEY,
    INCREMENTAL_DEAL_PROMPT_VERSION,
    build_prompt,
    deal_analysis_cache_options,
    load_incremental_context,
)
from openai_api.llm.analyze_deal_if_changed import incremental_context


def _canonical_state() -> dict:
    return {
        "owner": {"entity_id": "7"},
        "entities": {"deal:7": {"semantic": {"stage_id": "NEW"}}},
        "source_status": {},
    }


def _baseline(coverage: dict) -> dict:
    return {
        "analysis": {"deal_context": {}},
        "evidence_coverage": coverage,
    }


class IncrementalDealAnalysisTests(unittest.TestCase):
    def test_prompt_contains_only_trusted_baseline_and_supplied_deltas(self) -> None:
        prompt = build_prompt(
            "7",
            "old-unchanged-history",
            "old-unchanged-transcript",
            "synthetic-diagnostics",
            [(Path("synthetic-rules.md"), "synthetic-rule")],
            {"closed": False},
            incremental_context={
                "PREVIOUS_TRUSTED_COMPLETE_ANALYSIS": {"deal_state": {"summary": "synthetic-baseline"}},
                "CRM_SEMANTIC_DELTA": [{"key": "deal:7", "change_type": "UPDATED_MEANINGFUL"}],
                "NEW_OR_REVISED_CLIENT_EVIDENCE": [{
                    "evidence_id": "call:201", "text": "synthetic-new-evidence",
                }],
                "AVAILABLE_CLIENT_EVIDENCE_IDS": ["call:101", "call:201"],
                "CURRENT_REQUIRED_CRM_FACTS": {"stage_id": "SYNTHETIC:STAGE"},
            },
        )
        for marker in (
            "PREVIOUS_TRUSTED_COMPLETE_ANALYSIS",
            "CRM_SEMANTIC_DELTA",
            "NEW_OR_REVISED_CLIENT_EVIDENCE",
            "CURRENT_REQUIRED_CRM_FACTS",
            "AVAILABLE_CLIENT_EVIDENCE_IDS",
            "synthetic-baseline",
            "synthetic-new-evidence",
            "synthetic-rule",
        ):
            self.assertIn(marker, prompt)
        self.assertIn("не полный analysis JSON", prompt)
        self.assertIn("только PATCH", prompt)
        self.assertIn("не объясняй, почему они остались прежними", prompt)
        self.assertNotIn("полный текущий analysis JSON", prompt)
        self.assertIn("не отменяет их молча", prompt)
        self.assertIn("NEW_OR_REVISED_CLIENT_EVIDENCE", prompt)
        self.assertIn("Повышай basis_status или BANT timing до confirmed", prompt)
        self.assertIn("Исходящие текстовые активности не являются evidence разговора.", prompt)
        self.assertIn("голосового Max без транскрипта", prompt)
        self.assertIn("call:101", prompt)
        self.assertNotIn("old-unchanged-history", prompt)
        self.assertNotIn("old-unchanged-transcript", prompt)

    def test_incremental_context_loader_rejects_partial_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(json.dumps({"CRM_SEMANTIC_DELTA": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid shape"):
                load_incremental_context(str(path))

    def test_incremental_context_producer_matches_loader(self) -> None:
        context, _ = incremental_context(
            _baseline({
                "call:101": {"content_hash": "old", "revision": 1},
            }),
            _canonical_state(),
            {"entries": []},
            [
                {"evidence_id": "call:101", "content_hash": "old", "kind": "call_transcript"},
                {"evidence_id": "message:201", "content_hash": "legacy", "kind": "inbound_message",
                 "text": "Бюджет согласовали"},
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(json.dumps(context), encoding="utf-8")
            loaded = load_incremental_context(str(path))
        self.assertEqual(
            loaded["AVAILABLE_CLIENT_EVIDENCE_IDS"],
            ["call:101", "message:201"],
        )
        self.assertEqual(loaded["NEW_OR_REVISED_CLIENT_EVIDENCE"][0]["evidence_id"], "message:201")
        self.assertEqual(loaded["NEW_OR_REVISED_CLIENT_EVIDENCE"][0]["delta_kind"], "new_evidence")

    def test_new_inbound_message_enters_evidence_delta(self) -> None:
        context, coverage = incremental_context(
            _baseline({
                "message:100": {"content_hash": "old", "revision": 1, "kind": "inbound_message"},
            }),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "message:100",
                    "kind": "inbound_message",
                    "content_hash": "old",
                    "text": "старое",
                },
                {
                    "evidence_id": "message:201",
                    "kind": "inbound_message",
                    "content_hash": "new",
                    "text": "Бюджет согласовали",
                },
            ],
        )
        delta = context["NEW_OR_REVISED_CLIENT_EVIDENCE"]
        self.assertEqual(len(delta), 1)
        self.assertEqual(delta[0]["evidence_id"], "message:201")
        self.assertEqual(delta[0]["kind"], "inbound_message")
        self.assertEqual(delta[0]["text"], "Бюджет согласовали")
        self.assertEqual(delta[0]["delta_kind"], "new_evidence")
        self.assertEqual(delta[0]["revision"], 1)
        self.assertEqual(coverage["message:201"]["revision"], 1)
        self.assertEqual(context["AVAILABLE_CLIENT_EVIDENCE_IDS"], ["message:100", "message:201"])

    def test_new_inbound_email_enters_evidence_delta(self) -> None:
        context, coverage = incremental_context(
            _baseline({}),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "email:88",
                    "kind": "inbound_email",
                    "content_hash": "mail-new",
                    "text": "Решение дадим в пятницу",
                    "subject": "КП",
                },
            ],
        )
        delta = context["NEW_OR_REVISED_CLIENT_EVIDENCE"]
        self.assertEqual(len(delta), 1)
        self.assertEqual(delta[0]["evidence_id"], "email:88")
        self.assertEqual(delta[0]["kind"], "inbound_email")
        self.assertEqual(delta[0]["delta_kind"], "new_evidence")
        self.assertEqual(delta[0]["revision"], 1)
        self.assertEqual(coverage["email:88"]["content_hash"], "mail-new")

    def test_unchanged_covered_evidence_stays_out_of_delta(self) -> None:
        context, coverage = incremental_context(
            _baseline({
                "message:100": {"content_hash": "same", "revision": 2, "kind": "inbound_message"},
            }),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "message:100",
                    "kind": "inbound_message",
                    "content_hash": "same",
                    "text": "Без изменений",
                },
            ],
        )
        self.assertEqual(context["NEW_OR_REVISED_CLIENT_EVIDENCE"], [])
        self.assertEqual(coverage["message:100"]["revision"], 2)

    def test_revised_inbound_evidence_increments_revision(self) -> None:
        context, coverage = incremental_context(
            _baseline({
                "email:88": {"content_hash": "old-hash", "revision": 1, "kind": "inbound_email"},
            }),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "email:88",
                    "kind": "inbound_email",
                    "content_hash": "new-hash",
                    "text": "Обновлённый текст письма",
                },
            ],
        )
        delta = context["NEW_OR_REVISED_CLIENT_EVIDENCE"]
        self.assertEqual(len(delta), 1)
        self.assertEqual(delta[0]["evidence_id"], "email:88")
        self.assertEqual(delta[0]["delta_kind"], "evidence_revision")
        self.assertEqual(delta[0]["revision"], 2)
        self.assertEqual(coverage["email:88"]["content_hash"], "new-hash")
        self.assertEqual(coverage["email:88"]["revision"], 2)

    def test_call_without_transcript_kind_is_not_client_evidence_delta(self) -> None:
        context, coverage = incremental_context(
            _baseline({}),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "call:5",
                    "kind": "call",
                    "content_hash": "no-transcript",
                    "text": "",
                },
            ],
        )
        self.assertEqual(context["NEW_OR_REVISED_CLIENT_EVIDENCE"], [])
        self.assertEqual(context["AVAILABLE_CLIENT_EVIDENCE_IDS"], ["call:5"])
        self.assertNotIn("call:5", coverage)

    def test_outbound_kind_is_not_treated_as_client_evidence_delta(self) -> None:
        context, coverage = incremental_context(
            _baseline({}),
            _canonical_state(),
            {"entries": []},
            [
                {
                    "evidence_id": "message:9",
                    "kind": "outbound_message",
                    "content_hash": "out",
                    "text": "Напоминаю про КП",
                },
            ],
        )
        self.assertEqual(context["NEW_OR_REVISED_CLIENT_EVIDENCE"], [])
        self.assertEqual(context["AVAILABLE_CLIENT_EVIDENCE_IDS"], ["message:9"])
        self.assertNotIn("message:9", coverage)

    def test_incremental_shares_full_instruction_prefix(self) -> None:
        context = {
            "PREVIOUS_TRUSTED_COMPLETE_ANALYSIS": {"deal_state": {"summary": "synthetic-baseline"}},
            "CRM_SEMANTIC_DELTA": [],
            "NEW_OR_REVISED_CLIENT_EVIDENCE": [{"evidence_id": "call:201", "text": "synthetic-new-evidence"}],
            "AVAILABLE_CLIENT_EVIDENCE_IDS": ["call:201"],
            "CURRENT_REQUIRED_CRM_FACTS": {"stage_id": "SYNTHETIC:STAGE"},
        }
        kwargs = {
            "deal_id": "7",
            "history_text": "old-unchanged-history",
            "transcript_text": "old-unchanged-transcript",
            "context_diagnostics_text": "synthetic-diagnostics",
            "okf_sections": [(Path("synthetic-rules.md"), "synthetic-rule")],
            "stage_policy": {"closed": False},
        }
        full = build_prompt(**kwargs)
        incremental = build_prompt(**kwargs, incremental_context=context)
        marker_at = full.find(DEAL_ID_SECTION_MARKER)
        self.assertGreater(marker_at, 0)
        self.assertEqual(full[:marker_at], incremental[:incremental.find(DEAL_ID_SECTION_MARKER)])
        rules_at = incremental.find("<incremental_analysis_rules>")
        input_at = incremental.find("## INCREMENTAL INPUT")
        self.assertGreater(rules_at, incremental.find(DEAL_ID_SECTION_MARKER))
        self.assertGreater(input_at, rules_at)
        self.assertNotIn("<incremental_analysis_rules>", full[:marker_at])

    def test_incremental_prompt_version_stays_separate_from_openai_cache_key(self) -> None:
        self.assertEqual(INCREMENTAL_DEAL_PROMPT_VERSION, "neuro-rop:incremental-deal:v3")
        self.assertNotEqual(INCREMENTAL_DEAL_PROMPT_VERSION, DEAL_PROMPT_CACHE_KEY)
        self.assertIn("neuro-rop:incremental-deal:v1", COMPATIBLE_DEAL_PROMPT_VERSIONS)
        self.assertIn("neuro-rop:incremental-deal:v2", COMPATIBLE_DEAL_PROMPT_VERSIONS)
        self.assertIn(INCREMENTAL_DEAL_PROMPT_VERSION, COMPATIBLE_DEAL_PROMPT_VERSIONS)
        self.assertIn(DEAL_PROMPT_CACHE_KEY, COMPATIBLE_DEAL_PROMPT_VERSIONS)

    def test_incremental_openai_cache_shares_full_key_and_id_marker(self) -> None:
        key, markers = deal_analysis_cache_options(incremental=True, transcript_text="### Звонок 1\n")
        self.assertEqual(key, DEAL_PROMPT_CACHE_KEY)
        self.assertEqual(markers, [DEAL_ID_SECTION_MARKER])
        full_key, full_markers = deal_analysis_cache_options(
            incremental=False,
            transcript_text="### Звонок 1\n",
        )
        self.assertEqual(full_key, DEAL_PROMPT_CACHE_KEY)
        self.assertGreater(len(full_markers), 1)
        self.assertEqual(full_markers[0], DEAL_ID_SECTION_MARKER)


if __name__ == "__main__":
    unittest.main()
