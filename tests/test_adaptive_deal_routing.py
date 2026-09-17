from __future__ import annotations

import unittest

from openai_api.llm import analyze_deal_if_changed


class IncrementalSizeRoutingRemovedTests(unittest.TestCase):
    def test_size_ratio_no_longer_selects_full_or_patch(self) -> None:
        for name in (
            "INCREMENTAL_VARIABLE_SIZE_RATIO_THRESHOLD",
            "adaptive_variable_size_routing",
            "choose_safe_llm_mode_by_variable_size",
            "measure_incremental_variable_bytes",
            "measure_full_variable_bytes",
            "load_full_variable_texts",
        ):
            self.assertFalse(hasattr(analyze_deal_if_changed, name), name)


if __name__ == "__main__":
    unittest.main()
