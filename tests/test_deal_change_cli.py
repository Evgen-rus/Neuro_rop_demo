from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai_api.change_detection.decision_engine import (
    FIRST_FULL_ANALYSIS,
    FULL_LLM_ANALYSIS,
    INCREMENTAL_LLM_ANALYSIS,
    MINI_RECOMMENDATION_NO_LLM,
    SKIPPED_NO_CHANGES,
    ProcessingDecision,
)
from openai_api.llm import analyze_deal, analyze_deal_if_changed


class DealChangeCliTests(unittest.TestCase):
    def _run_main(
        self,
        root: Path,
        *,
        decision: ProcessingDecision,
        incremental_enabled: bool = False,
        stage5_error: Exception | None = None,
        analyzer_error: Exception | None = None,
        persistence_error: Exception | None = None,
        force_llm: bool = False,
        source_status: dict | None = None,
        trusted_baseline: bool | None = None,
    ) -> tuple[Mock, Mock]:
        args = SimpleNamespace(
            deal_id="7", deal_root=str(root), db_path=str(root / "state.sqlite"),
            transcript="none", model=None, force_llm=force_llm, dry_run_decision=False,
        )
        if trusted_baseline is None:
            trusted_baseline = incremental_enabled
        baseline = {
            "analysis_run_id": 1,
            "analysis": {"deal_state": {}},
            "canonical_fingerprint": "old",
            "evidence_coverage": {},
        } if trusted_baseline else None
        patches = (
            patch.object(analyze_deal_if_changed, "parse_args", return_value=args),
            patch.object(analyze_deal_if_changed, "load_dotenv"),
            patch.object(analyze_deal_if_changed, "init_db"),
            patch.object(analyze_deal_if_changed, "raw_bundle_path", return_value=root / "raw.json"),
            patch.object(analyze_deal_if_changed, "resolve_transcript_for_snapshot", return_value=(None, "none")),
            patch.object(analyze_deal_if_changed, "load_json", return_value={}),
            patch.object(analyze_deal_if_changed, "build_deal_snapshot", return_value={"deal": {}}),
            patch.object(analyze_deal_if_changed, "fingerprint_snapshot", return_value="new"),
            patch.object(analyze_deal_if_changed, "get_entity_state", return_value={"snapshot": {}, "last_analysis": {}}),
            patch.object(analyze_deal_if_changed, "get_trusted_deal_baseline", return_value=baseline),
            patch.object(analyze_deal_if_changed, "compare_snapshots", return_value=decision.diff),
            patch.object(analyze_deal_if_changed, "get_entity_memory", return_value=None),
            patch.object(analyze_deal_if_changed, "decide_deal_processing", return_value=decision),
            patch.object(analyze_deal_if_changed, "DEAL_INCREMENTAL_ANALYSIS_ENABLED", incremental_enabled),
            patch.object(analyze_deal_if_changed, "stage5_inputs", return_value=(
                baseline,
                {
                    "owner": {"entity_id": "7"},
                    "entities": {"deal:7": {"semantic": {}}},
                    "source_status": source_status or {},
                },
                {"entries": [], "from_semantic_fingerprint": "old", "to_semantic_fingerprint": "new"},
                [],
            ), side_effect=stage5_error),
            patch.object(
                analyze_deal_if_changed,
                "persist_successful_llm_run",
                return_value=1,
                side_effect=persistence_error,
            ),
            patch.object(analyze_deal_if_changed, "emit_deal_publish_ready"),
            patch.object(analyze_deal_if_changed, "save_analysis_run", return_value=2),
            patch.object(analyze_deal_if_changed, "run_existing_analyzer", side_effect=analyzer_error),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        try:
            analyze_deal_if_changed.main()
        except Exception:
            if persistence_error is None and stage5_error is None:
                raise
        return (
            analyze_deal_if_changed.run_existing_analyzer,
            analyze_deal_if_changed.persist_successful_llm_run,
        )

    def test_latest_transcript_ignores_generated_all_calls_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            transcripts = Path(temp_dir)
            source = transcripts / "call_42.md"
            aggregate = transcripts / "deal_7_all_calls_transcript.md"
            source.write_text("source", encoding="utf-8")
            aggregate.write_text("aggregate", encoding="utf-8")
            aggregate.touch()

            self.assertEqual(analyze_deal.latest_transcript(transcripts), source)
            self.assertEqual(analyze_deal_if_changed.latest_transcript_or_none(transcripts), source)

    def test_stage5_evidence_uses_the_normalized_messenger_ledger(self) -> None:
        normalized = [{"event_id": "crm_mirror:hash", "source_ids": ["3098173"]}]
        with (
            patch.object(analyze_deal_if_changed, "merge_deal_bundle", return_value=({}, {})),
            patch.object(analyze_deal_if_changed, "collect_deal_evidence", return_value=[]) as collect,
        ):
            analyze_deal_if_changed.stage5_inputs(
                Path("unused.sqlite"),
                deal_id="7",
                raw_bundle={"deal_id": "7"},
                current_deal_dir=Path("unused"),
                baseline=None,
                normalized_communications=normalized,
            )
        self.assertEqual(collect.call_args.args[0]["normalized_communications"], normalized)

    def test_dry_run_decision_does_not_save_snapshot_or_analysis_state(self) -> None:
        args = SimpleNamespace(
            deal_id="7",
            deal_root="unused",
            db_path=None,
            transcript="none",
            model=None,
            force_llm=False,
            dry_run_decision=True,
        )
        decision = Mock()
        decision.as_dict.return_value = {"status": "SKIPPED_NO_CHANGES"}
        with (
            patch.object(analyze_deal_if_changed, "parse_args", return_value=args),
            patch.object(analyze_deal_if_changed, "load_dotenv"),
            patch.object(analyze_deal_if_changed, "init_db"),
            patch.object(analyze_deal_if_changed, "raw_bundle_path", return_value=Path("raw.json")),
            patch.object(analyze_deal_if_changed, "resolve_transcript_for_snapshot", return_value=(None, "none")),
            patch.object(analyze_deal_if_changed, "load_json", return_value={}),
            patch.object(analyze_deal_if_changed, "build_deal_snapshot", return_value={"deal": {}}),
            patch.object(analyze_deal_if_changed, "fingerprint_snapshot", return_value="fingerprint"),
            patch.object(analyze_deal_if_changed, "get_entity_state", return_value=None),
            patch.object(analyze_deal_if_changed, "compare_snapshots", return_value={"changes": []}),
            patch.object(analyze_deal_if_changed, "get_entity_memory", return_value=None),
            patch.object(analyze_deal_if_changed, "decide_deal_processing", return_value=decision),
            patch.object(analyze_deal_if_changed, "save_json") as save_json,
            patch.object(analyze_deal_if_changed, "save_analysis_run") as save_analysis_run,
        ):
            analyze_deal_if_changed.main()

        save_json.assert_not_called()
        save_analysis_run.assert_not_called()

    def test_legacy_incremental_decision_runs_full_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, _persist = self._run_main(
                Path(directory),
                decision=ProcessingDecision(
                    status=INCREMENTAL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
            analyzer.assert_called_once()
            self.assertEqual(analyzer.call_args.args[1], "none")
            self.assertIsNone(analyzer.call_args.kwargs.get("incremental_context"))

    def test_opt_in_routes_incremental_and_persists_incremental(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        self.assertIsNotNone(analyzer.call_args.kwargs["incremental_context"])
        self.assertEqual(persist.call_args.kwargs["decision_status"], INCREMENTAL_LLM_ANALYSIS)

    def test_client_reply_routes_incremental_when_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["client reply"],
                    triggers=[],
                    diff={"changes": ["new_client_reply"], "details": {}},
                ),
            )
        self.assertIsNotNone(analyzer.call_args.kwargs["incremental_context"])
        self.assertEqual(persist.call_args.kwargs["decision_status"], INCREMENTAL_LLM_ANALYSIS)

    def test_normal_full_run_has_no_semantic_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                trusted_baseline=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["recovery"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        persist.assert_called_once()
        analyze_deal_if_changed.save_analysis_run.assert_not_called()

    def test_incremental_error_runs_exactly_one_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = 0

            def fail_first(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("synthetic incremental failure")

            analyzer, persist = self._run_main(
                root,
                incremental_enabled=True,
                analyzer_error=fail_first,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        self.assertEqual(analyzer.call_count, 2)
        self.assertIsNotNone(analyzer.call_args_list[0].kwargs["incremental_context"])
        self.assertIsNone(analyzer.call_args_list[1].kwargs.get("incremental_context"))
        self.assertTrue(persist.call_args.kwargs["decision_reason"]["fallback"])

    def test_technical_only_skip_never_calls_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, _persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=SKIPPED_NO_CHANGES,
                    reasons=["technical only"],
                    triggers=[],
                    diff={"changes": ["technical_only"], "details": {}},
                ),
            )
        analyzer.assert_not_called()

    def test_incremental_persistence_error_does_not_trigger_full(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                persistence_error=OSError("synthetic persistence failure"),
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        persist.assert_called_once()

    def test_stage5_preflight_error_stops_before_paid_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                stage5_error=ValueError("synthetic canonical metadata failure"),
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        analyzer.assert_not_called()
        persist.assert_not_called()

    def test_force_llm_keeps_full_with_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                force_llm=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["force"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        self.assertIsNone(analyzer.call_args.kwargs.get("incremental_context"))
        self.assertEqual(persist.call_args.kwargs["decision_status"], FULL_LLM_ANALYSIS)

    def test_commercial_refs_changed_keeps_full_when_baseline_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["commercial"],
                    triggers=[],
                    diff={"changes": ["commercial_refs_changed"], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        self.assertIsNone(analyzer.call_args.kwargs.get("incremental_context"))
        self.assertEqual(persist.call_args.kwargs["decision_status"], FULL_LLM_ANALYSIS)
        self.assertEqual(
            persist.call_args.kwargs["decision_reason"]["fallback_reason"],
            "commercial_delta_requires_full",
        )

    def test_incomplete_source_still_uses_patch_when_baseline_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                source_status={"activities": "failed"},
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["failed source"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        self.assertIsNotNone(analyzer.call_args.kwargs.get("incremental_context"))
        self.assertEqual(persist.call_args.kwargs["decision_status"], INCREMENTAL_LLM_ANALYSIS)

    def test_size_no_longer_falls_back_to_full(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        self.assertIsNotNone(analyzer.call_args.kwargs["incremental_context"])
        self.assertEqual(persist.call_args.kwargs["decision_status"], INCREMENTAL_LLM_ANALYSIS)
        reason = persist.call_args.kwargs["decision_reason"]
        self.assertNotIn("routing_size_ratio", reason)
        self.assertNotIn("chosen_analysis_mode", reason)
        self.assertNotEqual(reason.get("fallback_reason"), "incremental_variable_size_not_advantageous")

    def test_first_full_does_not_use_incremental(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                decision=ProcessingDecision(
                    status=FIRST_FULL_ANALYSIS,
                    reasons=["first analysis"],
                    triggers=[],
                    diff={"changes": [], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        self.assertIsNone(analyzer.call_args.kwargs.get("incremental_context"))
        self.assertEqual(persist.call_args.kwargs["decision_status"], FIRST_FULL_ANALYSIS)

    def test_unsafe_baseline_keeps_full(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer, persist = self._run_main(
                Path(directory),
                incremental_enabled=True,
                trusted_baseline=False,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        analyzer.assert_called_once()
        self.assertIsNone(analyzer.call_args.kwargs.get("incremental_context"))
        self.assertEqual(persist.call_args.kwargs["decision_status"], FULL_LLM_ANALYSIS)
        self.assertEqual(
            persist.call_args.kwargs["decision_reason"]["fallback_reason"],
            "unsafe_trusted_baseline",
        )

    def test_invalid_patch_error_file_marks_fallback_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            calls = 0
            error_path = analyze_deal_if_changed.analysis_paths(root / "deal_7", "7")["error"]

            def fail_with_patch_error(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    error_path.parent.mkdir(parents=True, exist_ok=True)
                    error_path.write_text(
                        json.dumps({"error_type": "incremental_patch_invalid"}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    raise RuntimeError("synthetic patch rejection")

            analyzer, persist = self._run_main(
                root,
                incremental_enabled=True,
                analyzer_error=fail_with_patch_error,
                decision=ProcessingDecision(
                    status=FULL_LLM_ANALYSIS,
                    reasons=["new evidence"],
                    triggers=[],
                    diff={"changes": ["transcript_changed"], "details": {}},
                ),
            )
        self.assertEqual(analyzer.call_count, 2)
        self.assertIsNotNone(analyzer.call_args_list[0].kwargs["incremental_context"])
        self.assertIsNone(analyzer.call_args_list[1].kwargs.get("incremental_context"))
        reason = persist.call_args.kwargs["decision_reason"]
        self.assertTrue(reason["fallback"])
        self.assertEqual(reason["fallback_reason"], "incremental_patch_invalid")
        self.assertEqual(reason["analysis_output_kind"], "incremental_patch_fallback_full")

    def test_mini_and_skip_do_not_call_analyzer(self) -> None:
        cases = (
            ProcessingDecision(
                status=MINI_RECOMMENDATION_NO_LLM,
                reasons=["soft change"],
                triggers=[{"trigger_type": "stale_activity"}],
                diff={"changes": ["new_comment"], "details": {}},
            ),
            ProcessingDecision(
                status=SKIPPED_NO_CHANGES,
                reasons=["no changes"],
                triggers=[],
                diff={"changes": [], "details": {}},
            ),
        )
        for decision in cases:
            with self.subTest(status=decision.status), tempfile.TemporaryDirectory() as directory:
                extra_patches = []
                if decision.status == MINI_RECOMMENDATION_NO_LLM:
                    extra_patches = [
                        patch.object(
                            analyze_deal_if_changed,
                            "filter_today_mini_triggers",
                            return_value=decision.triggers,
                        ),
                        patch.object(
                            analyze_deal_if_changed,
                            "render_mini_recommendation",
                            return_value="mini",
                        ),
                        patch.object(analyze_deal_if_changed, "save_mini_recommendation_markdown"),
                        patch.object(analyze_deal_if_changed, "save_mini_recommendation"),
                        patch.object(analyze_deal_if_changed, "persist_skip", return_value=3),
                    ]
                started = [item.start() for item in extra_patches]
                try:
                    analyzer, _persist = self._run_main(
                        Path(directory),
                        incremental_enabled=True,
                        decision=decision,
                    )
                    analyzer.assert_not_called()
                finally:
                    for item in reversed(extra_patches):
                        item.stop()
                    del started


if __name__ == "__main__":
    unittest.main()
