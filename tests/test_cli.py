import contextlib
import os
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_generate import dataset
from test_geolite import archive
from nginx_country.__main__ import main


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def prepare(root, ipdeny_ipv6=False):
    payload = json.dumps({'countryCode': 'FR', 'prefixes': {'ipv4': ['192.0.2.0/24'], 'ipv6': ['2001:db8::/32']}})
    dataset(root / 'raw', 'ipverse', [('fr.json', 'FR', payload)])
    entries = [('ipv4/fr-aggregated.zone', 'FR', '192.0.2.0/25\n')]
    dataset(root / 'raw', 'ipdeny', entries)
    archive(root / 'geo.zip')


class CliTests(unittest.TestCase):
    def test_help_lists_every_subcommand(self):
        code, out, _ = run('--help')
        self.assertEqual(code, 0)
        for name in ('collect', 'generate', 'compare', 'compare-three', 'build-combined'):
            self.assertIn(name, out)

    def test_unknown_command_is_rejected_with_usage_error(self):
        code, _, err = run('inconnu')
        self.assertEqual(code, 2)
        self.assertNotIn('Traceback', err)

    def test_collect_rejects_invalid_country_without_network(self):
        code, _, err = run('collect', 'france')
        self.assertEqual(code, 2)
        self.assertIn('deux lettres', err)

    def test_legacy_country_argument_is_routed_to_collect(self):
        code, _, err = run('FRANCE')
        self.assertEqual(code, 2)
        self.assertIn('deux lettres', err)

    def test_generate_writes_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            code, out, _ = run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'))
            self.assertEqual(code, 0)
            self.assertIn('ipverse', out)
            self.assertIn('ipdeny', out)

    def test_generate_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            code, out, _ = run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'), '--dry-run')
            self.assertEqual(code, 0)
            self.assertIn('simulation', out)
            self.assertFalse((root / 'generated').exists())

    def test_compare_outputs_json_for_one_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'))
            code, out, _ = run('compare', '--input', str(root / 'generated'), '--country', 'FR')
            self.assertEqual(code, 0)
            self.assertIn('FR', json.loads(out)['countries'])

    def test_compare_reports_missing_input_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run('compare', '--input', str(Path(tmp) / 'absent'))
            self.assertEqual(code, 1)
            self.assertNotIn('Traceback', err)

    def test_build_combined_succeeds_when_a_family_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'))
            code, out, err = run('build-combined', '--input', str(root / 'generated'), '--geolite', str(root / 'geo.zip'), '--output', str(root / 'out'))
            self.assertEqual(code, 0, err)
            self.assertIn('partielles', out)
            self.assertIn('allow 2001:db8::/32;', (root / 'out/FR-allow.conf').read_text())

    def test_build_combined_reports_invalid_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'))
            (root / 'bad.zip').write_bytes(b'invalid')
            code, _, err = run('build-combined', '--input', str(root / 'generated'), '--geolite', str(root / 'bad.zip'), '--output', str(root / 'out'))
            self.assertEqual(code, 1)
            self.assertNotIn('Traceback', err)

    def test_collect_geolite_without_credentials_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            code, _, err = run('collect-geolite', '--env-file', str(Path(tmp) / '.env'), '--output', str(Path(tmp) / 'geo'))
            self.assertEqual(code, 1)
            self.assertIn('MAXMIND_LICENSE_KEY', err)
            self.assertNotIn('Traceback', err)

    def test_build_combined_uses_latest_geolite_archive_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            run('generate', '--input', str(root / 'raw'), '--output', str(root / 'generated'))
            (root / 'geo').mkdir()
            (root / 'geo/GeoLite2-Country-CSV_20261117.zip').write_bytes((root / 'geo.zip').read_bytes())
            code, _, err = run('build-combined', '--input', str(root / 'generated'), '--geolite-dir', str(root / 'geo'), '--output', str(root / 'out'))
            self.assertEqual(code, 0, err)
            self.assertTrue((root / 'out/FR-allow.conf').exists())

    def test_update_skip_fetch_runs_generate_then_build_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            (root / 'raw/geolite').mkdir()
            (root / 'raw/geolite/GeoLite2-Country-CSV_20261117.zip').write_bytes((root / 'geo.zip').read_bytes())
            code, out, err = run('update', '--skip-fetch', '--data', str(root / 'raw'), '--generated', str(root / 'generated'), '--output', str(root / 'out'))
            self.assertEqual(code, 0, err)
            self.assertTrue((root / 'generated/ipverse').exists())
            self.assertIn('allow 192.0.2.0/24;', (root / 'out/FR-allow.conf').read_text())

    def test_update_stops_when_generation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, _, _ = run('update', '--skip-fetch', '--data', str(root / 'vide'), '--generated', str(root / 'g'), '--output', str(root / 'out'))
            self.assertEqual(code, 1)
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
