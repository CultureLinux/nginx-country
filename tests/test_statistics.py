import unittest
from scripts.statistics_report import summarize

class StatisticsTests(unittest.TestCase):
    def test_summary_excludes_absent_and_empty_union_and_weights_countries_equally(self):
        data = {'countries': {
            'FR': {'ipv4': {'jaccard': .8}, 'ipv6': {'jaccard': None}},
            'DE': {'ipv4': {'jaccard': .4}, 'ipv6': {'comparison': None}},
            'GB': {'ipv4': {'comparison': None}, 'ipv6': {'jaccard': 1.0}},
        }}
        summary = summarize(data)
        self.assertEqual(summary['ipv4']['count'], 2)
        self.assertAlmostEqual(summary['ipv4']['mean'], .6)
        self.assertEqual(summary['ipv4']['missing'], 1)
        self.assertEqual(summary['ipv6']['undefined'], 1)
        self.assertEqual(summary['ipv6']['missing'], 1)
        self.assertEqual(summary['ipv6']['count'], 1)
