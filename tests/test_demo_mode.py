from __future__ import annotations

import inspect
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app_clock import (
    app_now,
    business_date,
    is_demo_mode,
    resolve_knowledge_dir,
    resolve_persisted_path,
    runtime_info,
)
from setup import BASE_DIR, MSK_TZ
from api.daytime_cycle import daytime_cycle_enabled, start_daytime_cycle, stop_daytime_cycle
from api.deal_control import (
    _deadline_bucket,
    build_deal_control_dashboard,
    build_deal_control_deal,
    load_deal_comments,
    refresh_deal_control,
)
from bitrix.client import BitrixDemoBlockedError, BitrixReadOnlyClient
from bitrix.deals.download_deals_call_audio import try_download_url
from storage.rop_db import init_db, save_ui_report, upsert_deal_control_deal
from tests.test_bitrix_usage_trace import FakeResponse, NO_RETRY
from tests.test_deal_manager_quick_help import ImmediateThread


DEMO_NOW = "2026-09-18T18:00:00+03:00"
DEMO_ENV = {"DEMO_MODE": "true", "DEMO_NOW": DEMO_NOW}


class DemoModeClockTests(unittest.TestCase):
    def test_production_flag_off_keeps_live_clock(self) -> None:
        with patch.dict(os.environ, {"DEMO_MODE": "false"}, clear=False):
            self.assertFalse(is_demo_mode())
            before = datetime.now(MSK_TZ)
            current = app_now()
            after = datetime.now(MSK_TZ)
            self.assertLessEqual(abs((current - before).total_seconds()), 2)
            self.assertLessEqual(abs((after - current).total_seconds()), 2)
            self.assertEqual(business_date(), current.date())

    def test_demo_clock_returns_demo_now_and_business_date(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False):
            self.assertTrue(is_demo_mode())
            current = app_now()
            self.assertEqual(current, datetime.fromisoformat(DEMO_NOW))
            self.assertEqual(business_date(), datetime.fromisoformat(DEMO_NOW).date())
            info = runtime_info()
            self.assertTrue(info["demo_mode"])
            self.assertEqual(info["current_business_datetime"], DEMO_NOW)
            self.assertEqual(info["business_date"], "2026-09-18")


class DemoModeBitrixGuardTests(unittest.TestCase):
    def test_production_call_still_reaches_http(self) -> None:
        with patch.dict(os.environ, {"DEMO_MODE": "false"}, clear=False), \
             patch("bitrix.client.requests.post", return_value=FakeResponse(200, {"result": []})) as post, \
             patch("bitrix.client.append_trace_event"):
            client = BitrixReadOnlyClient("https://example.invalid/rest/hook", retry_policy=NO_RETRY)
            data = client.call("crm.deal.list", {"filter": {"CLOSED": "N"}})
        self.assertEqual(data["result"], [])
        post.assert_called_once()

    def test_demo_blocks_rest_before_network(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False), \
             patch("bitrix.client.requests.post", side_effect=AssertionError("HTTP must not run")) as post, \
             patch("bitrix.client.append_trace_event"):
            client = BitrixReadOnlyClient("https://example.invalid/rest/hook", retry_policy=NO_RETRY)
            with self.assertRaises(BitrixDemoBlockedError):
                client.call("crm.deal.list", {"filter": {"CLOSED": "N"}})
        post.assert_not_called()

    def test_demo_blocks_audio_download_before_network(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False), \
             patch("bitrix.deals.download_deals_call_audio.requests.get", side_effect=AssertionError("HTTP must not run")) as get:
            with self.assertRaises(BitrixDemoBlockedError):
                try_download_url("https://example.invalid/file.mp3", Path("tmp"), "call.mp3")
        get.assert_not_called()


class DemoModeSchedulerTests(unittest.TestCase):
    def test_demo_disables_cycle_even_if_env_enables_it(self) -> None:
        with patch.dict(os.environ, {**DEMO_ENV, "DAYTIME_CYCLE_ENABLED": "true"}, clear=False):
            self.assertFalse(daytime_cycle_enabled())
            start_daytime_cycle()
            try:
                from api import daytime_cycle as module

                self.assertTrue(module._thread is None or not module._thread.is_alive())
            finally:
                stop_daytime_cycle(timeout=1)


class DemoModeDealControlTests(unittest.TestCase):
    def test_today_tomorrow_overdue_use_demo_now(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False):
            now = app_now()
            self.assertEqual(_deadline_bucket(now - timedelta(hours=1), now), "overdue")
            self.assertEqual(_deadline_bucket(now.replace(hour=20), now), "today")
            tomorrow = now + timedelta(days=1)
            self.assertEqual(_deadline_bucket(tomorrow.replace(hour=10), now), "tomorrow")
            future = now + timedelta(days=2)
            self.assertEqual(_deadline_bucket(future.replace(hour=10), now), "future")

    def test_read_path_and_saved_full_analysis_do_not_need_bitrix(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False), tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "demo.sqlite"
            init_db(db_path)
            upsert_deal_control_deal(
                db_path,
                deal_id="101",
                source="initial",
                title="Сделка 101",
                manager_id="10",
                manager_name="Иванов Иван",
                stage_id="C15:NEW",
                stage_name="Новая",
                pipeline_id="15",
                amount="120000",
                currency_id="RUB",
                created_at_crm="2026-09-17T09:00:00+03:00",
                modified_at_crm="2026-09-18T09:00:00+03:00",
                is_active=True,
            )
            save_ui_report(
                db_path,
                entity_type="deal",
                entity_id="101",
                report_json={
                    "deal_control_brief": {
                        "current_situation": "Клиент ждёт КП",
                        "manager_coaching": "Позвонить сегодня",
                    }
                },
            )
            with patch("api.deal_control.make_client", side_effect=AssertionError("Bitrix must not run")):
                dashboard = build_deal_control_dashboard(db_path=db_path)
                deal = build_deal_control_deal(db_path=db_path, deal_id="101")
                comments = load_deal_comments(deal_id="101")
                synced = refresh_deal_control(db_path=db_path)
            self.assertEqual(dashboard["deals"][0]["deal_id"], "101")
            self.assertEqual(deal["coaching"]["current_situation"], "Клиент ждёт КП")
            self.assertFalse(comments["available"])
            self.assertIn("DEMO_MODE", synced.get("sync_message") or "")

    def test_runtime_endpoint_exposes_demo_clock(self) -> None:
        with patch.dict(os.environ, DEMO_ENV, clear=False):
            from api.app import _PUBLIC_PATHS, runtime

            payload = runtime()
        self.assertIn("/api/runtime", _PUBLIC_PATHS)
        self.assertTrue(payload["demo_mode"])
        self.assertEqual(payload["current_business_datetime"], DEMO_NOW)
        self.assertEqual(payload["business_date"], "2026-09-18")


class DemoModePathResolutionTests(unittest.TestCase):
    def test_production_keeps_container_paths(self) -> None:
        stored = "/app/reports/rop_assistant/deals/deal_1/analysis/deal_1_rop_report.md"
        with patch.dict(os.environ, {"DEMO_MODE": "false"}, clear=False):
            self.assertEqual(resolve_persisted_path(stored), Path(stored))
            self.assertEqual(
                resolve_knowledge_dir(),
                BASE_DIR / "knowledge" / "clients" / "praktikm",
            )

    def test_demo_maps_app_reports_to_local_tree(self) -> None:
        stored = "/app/reports/rop_assistant/deals/deal_1/analysis/deal_1_rop_report.md"
        with patch.dict(os.environ, DEMO_ENV, clear=False):
            mapped = resolve_persisted_path(stored)
            self.assertEqual(
                mapped,
                BASE_DIR / "reports" / "rop_assistant" / "deals" / "deal_1" / "analysis" / "deal_1_rop_report.md",
            )
            local = BASE_DIR / "reports" / "local.md"
            self.assertEqual(resolve_persisted_path(str(local)), local)

    def test_demo_maps_knowledge_to_runtime_copy_when_present(self) -> None:
        stored = "/app/knowledge/clients/praktikm/manager_tactics.md"
        with patch.dict(os.environ, DEMO_ENV, clear=False), tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "runtime" / "knowledge"
            runtime_file = runtime_root / "clients" / "praktikm" / "manager_tactics.md"
            runtime_file.parent.mkdir(parents=True, exist_ok=True)
            runtime_file.write_text("tactics", encoding="utf-8")
            with patch("app_clock.BASE_DIR", Path(directory)):
                self.assertEqual(resolve_persisted_path(stored), runtime_file)
                self.assertEqual(
                    resolve_knowledge_dir(),
                    Path(directory) / "runtime" / "knowledge" / "clients" / "praktikm",
                )


class DemoModeLlmTests(unittest.TestCase):
    def test_demo_mode_does_not_gate_quick_help_entry(self) -> None:
        from api.deal_manager_quick_help import start_quick_help_job

        self.assertNotIn("is_demo_mode", inspect.getsource(start_quick_help_job))
        self.assertNotIn("DEMO_MODE", inspect.getsource(start_quick_help_job))

    def test_companion_uses_local_context_without_analyze(self) -> None:
        from api import deal_manager_companion as companion_api
        from tests.test_deal_manager_companion import COMPANION, CONTEXT, LAST_CONTACT

        with patch.dict(os.environ, DEMO_ENV, clear=False), \
             patch.object(companion_api, "find_last_contact", return_value=LAST_CONTACT), \
             patch.object(companion_api, "_run_analyze", side_effect=AssertionError("analyze must not run")) as analyze, \
             patch.object(companion_api, "_load_context", return_value=CONTEXT), \
             patch.object(companion_api, "_cached", return_value=None), \
             patch.object(companion_api, "generate_deal_manager_companion", return_value=(COMPANION, {"model": "test"})), \
             patch.object(companion_api.threading, "Thread", ImmediateThread), \
             patch.object(companion_api, "_storage_call", return_value={"id": 3}):
            result = companion_api.start_companion_job(
                db_path=Path("state.sqlite"), deal_id="101", confirm_paid=True,
            )
        analyze.assert_not_called()
        self.assertEqual(result["companion_id"], 3)
        self.assertEqual(result["status"], "done")


if __name__ == "__main__":
    unittest.main()
