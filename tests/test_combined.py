import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_generate import dataset
from test_geolite import archive
from nginx_country.generate import generate_source


class CombinedTests(unittest.TestCase):
    def test_union_and_intersection_and_missing_family(self):
        from nginx_country.combined import build_combined
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); archive(root/'geo.zip')
            payload=json.dumps({'countryCode':'FR','prefixes':{'ipv4':['192.0.2.0/24'],'ipv6':['2001:db8::/32']}})
            dataset(root/'raw','ipverse',[('fr.json','FR',payload)])
            dataset(root/'raw','ipdeny',[('ipv4/fr-aggregated.zone','FR','192.0.2.0/26\n')])
            for source in ('ipverse','ipdeny'): generate_source(root/'raw',root/'generated',source)
            report=build_combined(root/'generated',root/'geo.zip',root/'nginx-country')
            allow=(root/'nginx-country/FR-allow.conf').read_text()
            deny=(root/'nginx-country/FR-deny.conf').read_text()
            self.assertIn('allow 192.0.2.0/24;',allow)
            self.assertIn('deny 192.0.2.0/26;',deny)
            self.assertNotIn('2001:db8',allow)
            self.assertNotIn('2001:db8',deny)
            self.assertEqual(report['countries']['FR']['ipv6']['status'],'incomplete')
            self.assertNotIn('deny all;',deny)

    def test_refuses_to_replace_unowned_directory(self):
        from nginx_country.combined import build_combined
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'output').mkdir(); (root/'output/user-file').write_text('keep')
            with self.assertRaises((OSError, ValueError)):
                build_combined(root/'missing',root/'bad.zip',root/'output')
            self.assertEqual((root/'output/user-file').read_text(),'keep')
