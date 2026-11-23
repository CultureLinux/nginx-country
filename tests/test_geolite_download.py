import http.server
import io
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from test_geolite import archive

ACCOUNT, KEY = '123456', 'cle-secrete-de-test'


def zip_bytes():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'geo.zip'
        archive(path)
        return path.read_bytes()


class Server:
    """Serveur local imitant MaxMind : Basic auth, puis redirection vers une URL signée."""

    def __init__(self, payload, status=200):
        self.payload, self.status, self.seen = payload, status, []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.seen.append((self.path, self.headers.get('Authorization')))
                if self.path.startswith('/geoip'):
                    if outer.status != 200:
                        self.send_response(outer.status); self.end_headers(); return
                    self.send_response(302); self.send_header('Location', '/signed?x=1'); self.end_headers()
                elif self.path.startswith('/signed'):
                    self.send_response(200)
                    self.send_header('Content-Disposition', 'attachment; filename=GeoLite2-Country-CSV_20261117.zip')
                    self.send_header('Content-Length', str(len(outer.payload)))
                    self.end_headers(); self.wfile.write(outer.payload)

        self.httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_port}/geoip'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


class DownloadTests(unittest.TestCase):
    def serve(self, payload, status=200):
        server = Server(payload, status)
        self.addCleanup(server.close)
        return server

    def tmpdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_downloads_validates_and_names_archive(self):
        from nginx_country.geolite_download import download_geolite
        server, out = self.serve(zip_bytes()), self.tmpdir()
        path = download_geolite(ACCOUNT, KEY, out, url=server.url)
        self.assertEqual(path.name, 'GeoLite2-Country-CSV_20261117.zip')
        self.assertTrue(zipfile.is_zipfile(path))

    def test_credentials_are_not_forwarded_to_redirect_target(self):
        import base64
        from nginx_country.geolite_download import download_geolite
        server, out = self.serve(zip_bytes()), self.tmpdir()
        download_geolite(ACCOUNT, KEY, out, url=server.url)
        first, second = server.seen
        self.assertEqual(first[1], 'Basic ' + base64.b64encode(f'{ACCOUNT}:{KEY}'.encode()).decode())
        self.assertIsNone(second[1])

    def test_invalid_archive_is_rejected_and_old_one_kept(self):
        from nginx_country.geolite_download import download_geolite
        server, out = self.serve(b'pas un zip'), self.tmpdir()
        old = out / 'GeoLite2-Country-CSV_20261020.zip'
        old.write_bytes(zip_bytes())
        with self.assertRaises(ValueError):
            download_geolite(ACCOUNT, KEY, out, url=server.url)
        self.assertTrue(old.exists())
        self.assertEqual([p.name for p in out.iterdir()], [old.name])

    def test_old_archives_are_removed_after_success(self):
        from nginx_country.geolite_download import download_geolite
        server, out = self.serve(zip_bytes()), self.tmpdir()
        old = out / 'GeoLite2-Country-CSV_20261020.zip'
        old.write_bytes(b'ancien')
        other = out / 'notes.txt'
        other.write_text('garder')
        download_geolite(ACCOUNT, KEY, out, url=server.url)
        self.assertFalse(old.exists())
        self.assertTrue(other.exists())

    def test_http_error_message_never_contains_the_key(self):
        from nginx_country.geolite_download import download_geolite
        server, out = self.serve(b'', status=401), self.tmpdir()
        with self.assertRaises(ValueError) as ctx:
            download_geolite(ACCOUNT, KEY, out, url=server.url)
        self.assertIn('401', str(ctx.exception))
        self.assertNotIn(KEY, str(ctx.exception))

    def test_missing_credentials_are_reported_without_network(self):
        from nginx_country.geolite_download import credentials_from_env
        with self.assertRaises(ValueError) as ctx:
            credentials_from_env({})
        self.assertIn('MAXMIND_LICENSE_KEY', str(ctx.exception))
        self.assertEqual(credentials_from_env({'MAXMIND_ACCOUNT_ID': ' 1 ', 'MAXMIND_LICENSE_KEY': 'k'}), ('1', 'k'))

    def test_https_is_required_except_for_loopback(self):
        from nginx_country.geolite_download import download_geolite
        with self.assertRaises(ValueError):
            download_geolite(ACCOUNT, KEY, self.tmpdir(), url='http://example.com/x')

    def test_latest_archive_picks_most_recent_date(self):
        from nginx_country.geolite_download import latest_geolite
        out = self.tmpdir()
        for name in ('GeoLite2-Country-CSV_20261020.zip', 'GeoLite2-Country-CSV_20261117.zip', 'autre.zip'):
            (out / name).write_bytes(b'x')
        self.assertEqual(latest_geolite(out).name, 'GeoLite2-Country-CSV_20261117.zip')
        with self.assertRaises(ValueError):
            latest_geolite(self.tmpdir())


if __name__ == '__main__':
    unittest.main()
