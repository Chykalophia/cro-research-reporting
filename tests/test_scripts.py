"""Tests for the plugin's deterministic scripts. Run: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("skills/experiment-design/scripts", "skills/voc-research/scripts",
            "skills/report-information-design/scripts"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import _stats  # noqa: E402
import agreement  # noqa: E402
import check_citations  # noqa: E402
import power  # noqa: E402
import readout  # noqa: E402
import srm_check  # noqa: E402
import test_log  # noqa: E402


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


class StatsTests(unittest.TestCase):
    def test_chi2_matches_tables(self):
        self.assertAlmostEqual(_stats.chi2_sf(3.841, 1), 0.05, places=3)
        self.assertAlmostEqual(_stats.chi2_sf(5.991, 2), 0.05, places=3)
        self.assertAlmostEqual(_stats.chi2_sf(11.07, 5), 0.05, places=3)

    def test_retrodesign_matches_gelman_carlin(self):
        # Gelman & Carlin 2014 example: true effect 2, se 8.1 -> power ~0.06, Type S ~24%, exaggeration ~9.5-9.7
        d = _stats.retrodesign(2, 8.1)
        self.assertAlmostEqual(d["power"], 0.06, delta=0.01)
        self.assertAlmostEqual(d["type_s"], 0.24, delta=0.02)
        self.assertTrue(9.0 < d["exaggeration"] < 10.2)


class PowerTests(unittest.TestCase):
    def test_conversion_sample_size(self):
        # 2.5% baseline, +10% relative, 80% power, alpha 0.05: ~64k per arm (cf. Evan Miller's calculator)
        n = power.n_per_arm_prop(0.025, 0.10, 0.05, 0.8)
        self.assertTrue(63000 < n < 65500, n)

    def test_cuped_reduces_sample(self):
        full = power.n_per_arm_mean(2.4, 18.5, 0.05, 0.05, 0.8)
        cuped = power.n_per_arm_mean(2.4, 18.5, 0.05, 0.05, 0.8, var_mult=0.75)
        self.assertAlmostEqual(cuped / full, 0.75, places=2)

    def test_mde_mode_inverts_size_mode(self):
        out = quiet(power.main, ["mde", "--baseline", "0.025", "--daily-visitors", "4000", "--max-days", "28", "--json"])
        m = out["detectable_mde_relative"]
        n = power.n_per_arm_prop(0.025, m, 0.05, 0.8)
        self.assertLessEqual(n, out["n_per_arm_available"])

    def test_variants_adjust_alpha(self):
        out = quiet(power.main, ["size", "--baseline", "0.03", "--mde", "0.1", "--variants", "3", "--json"])
        self.assertAlmostEqual(out["alpha_per_comparison"], 0.05 / 3)


class SrmTests(unittest.TestCase):
    def test_flags_mismatch(self):
        self.assertTrue(srm_check.srm([50211, 49123])["srm"])

    def test_passes_even_split(self):
        self.assertFalse(srm_check.srm([50000, 50100])["srm"])

    def test_weighted_split(self):
        self.assertFalse(srm_check.srm([20000, 80000], [20, 80])["srm"])


class ReadoutTests(unittest.TestCase):
    def test_clear_win_ships(self):
        out = quiet(readout.main, ["--control", "50000", "1000", "--variant", "50000", "1200", "--json"])
        v = out["variants"][0]
        self.assertEqual(v["decision"], "SHIP")
        self.assertTrue(v["rel_ci"][0] > 0)

    def test_srm_blocks_decision(self):
        out = quiet(readout.main, ["--control", "52000", "1000", "--variant", "48000", "1200", "--json"])
        self.assertEqual(out["variants"][0]["decision"], "DO NOT READ (SRM)")

    def test_guardrail_failure_blocks_ship(self):
        out = quiet(readout.main, ["--control", "50000", "1000", "--variant", "50000", "1200",
                                   "--guardrail", "aov,1000,500,1200,450,0.02", "--json"])
        self.assertEqual(out["variants"][0]["decision"], "DO NOT SHIP (guardrail)")

    def test_inconclusive(self):
        out = quiet(readout.main, ["--control", "48210", "1205", "--variant", "48530", "1302", "--json"])
        self.assertEqual(out["variants"][0]["decision"], "INCONCLUSIVE")

    def test_rel_ci_contains_estimate(self):
        r = readout.compare_prop(48210, 1205, 48530, 1302, 0.05)
        self.assertTrue(r["rel_ci"][0] < r["rel_lift"] < r["rel_ci"][1])


class TestLogTests(unittest.TestCase):
    def test_round_trip_and_prior(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.csv")
            base = ["--log", log, "add", "--page", "pdp", "--hypothesis", "h, with comma"]
            quiet(test_log.main, base + ["--id", "T1", "--lever", "Trust", "--outcome", "win"])
            quiet(test_log.main, base + ["--id", "T2", "--lever", "Trust", "--outcome", "flat"])
            quiet(test_log.main, base + ["--id", "T3", "--lever", "Trust", "--outcome", "invalid"])
            rows = test_log.read(log)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["hypothesis"], "h, with comma")
            g = test_log.rates(rows, "lever")["Trust"]
            self.assertEqual((g["n"], g["win"]), (2, 1))
            self.assertAlmostEqual(test_log.prior(1, 2), 2 / 7)


class AgreementTests(unittest.TestCase):
    def test_kappa_known_value(self):
        a = ["cost", "fit", "fit", "trust", "cost", "other", "fit", "trust"]
        b = ["cost", "fit", "quality", "trust", "cost", "fit", "fit", "trust"]
        k, po = agreement.kappa(a, b)
        self.assertAlmostEqual(po, 0.75)
        self.assertAlmostEqual(k, (0.75 - 17 / 64) / (1 - 17 / 64), places=6)

    def test_perfect_agreement(self):
        k, _ = agreement.kappa(["a", "b"], ["a", "b"])
        self.assertAlmostEqual(k, 1.0)


class CitationTests(unittest.TestCase):
    def test_extract_and_dedupe(self):
        text = 'a <a href="https://x.org/a">x</a> https://x.org/a. and (https://y.org/b) https://fonts.googleapis.com/css'
        self.assertEqual(check_citations.extract_urls(text), ["https://x.org/a", "https://y.org/b"])

    def test_footnote_integrity(self):
        text = '<a href="#s-1">1</a><a href="#s-4">4</a><li id="s-1"></li><li id="s-3"></li>'
        f = check_citations.footnote_integrity(text)
        self.assertEqual(f["refs_without_entry"], ["s-4"])
        self.assertEqual(f["entries_never_cited"], ["s-3"])
        self.assertEqual(f["numbering_gaps"], [2])

    def test_classify(self):
        self.assertEqual(check_citations.classify({"status": 200}), "ok")
        self.assertEqual(check_citations.classify({"status": 404}), "dead")
        self.assertTrue(check_citations.classify({"status": 403}).startswith("blocked"))
        self.assertEqual(check_citations.classify({"status": None}), "error")


if __name__ == "__main__":
    unittest.main()
