from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import analysis_cache as cache


class AnalysisCacheTests(unittest.TestCase):
    def setUp(self):
        cache._values.clear()
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'adapter.py'; self.source.write_text('version 1')
        self.calls = []

    def analyzer(self):
        @cache.content_analysis(self.source)
        def analyze(raw):
            self.calls.append(raw)
            if raw == b'bad': raise ValueError('invalid bytes')
            return {'nested': [raw.hex()]}
        return analyze

    def test_exact_content_reused_but_result_mutations_isolated(self):
        analyze = self.analyzer(); first = analyze(b'good')
        first['nested'].clear()
        self.assertEqual(analyze(bytearray(b'good')), {'nested': ['676f6f64']})
        self.assertEqual(len(self.calls), 1)

    def test_changed_input_reanalyzed_and_failures_never_cached(self):
        analyze = self.analyzer(); raw = bytearray(b'good'); analyze(raw); raw[0] = 0
        analyze(raw)
        for _ in range(2):
            with self.assertRaises(ValueError): analyze(b'bad')
        self.assertEqual(len(self.calls), 4)

    def test_reload_reuses_only_same_source_and_content(self):
        self.analyzer()(b'good'); self.analyzer()(b'good')
        self.assertEqual(len(self.calls), 1)
        self.source.write_text('version 2')
        self.analyzer()(b'good')
        self.assertEqual(len(self.calls), 2)

    def test_bounded_eviction_recomputes_old_input(self):
        analyze = self.analyzer()
        for n in range(cache.LIMIT + 1): analyze(bytes([n]))
        self.assertEqual(len(cache._values), cache.LIMIT)
        analyze(b'\x00')
        self.assertEqual(len(self.calls), cache.LIMIT + 2)

if __name__ == '__main__': unittest.main()
