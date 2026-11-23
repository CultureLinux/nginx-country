import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class EnvTests(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / '.env'
        path.write_text(text, encoding='utf-8')
        return path

    def test_parses_values_comments_quotes_and_export(self):
        from nginx_country.env import read_env_file
        path = self.write('# commentaire\n\nA=1\nexport B="deux mots"\nC=\'x\'\nD = spaced \nBAD LINE\n')
        self.assertEqual(read_env_file(path), {'A': '1', 'B': 'deux mots', 'C': 'x', 'D': 'spaced'})

    def test_missing_file_gives_empty_mapping(self):
        from nginx_country.env import read_env_file
        self.assertEqual(read_env_file(Path('/nonexistent/.env')), {})

    def test_environment_variable_wins_over_file(self):
        from nginx_country.env import load_env
        path = self.write('NC_TEST_A=fichier\nNC_TEST_B=fichier\n')
        with mock.patch.dict(os.environ, {'NC_TEST_A': 'shell'}, clear=False):
            os.environ.pop('NC_TEST_B', None)
            load_env(path)
            self.assertEqual(os.environ['NC_TEST_A'], 'shell')
            self.assertEqual(os.environ['NC_TEST_B'], 'fichier')
            os.environ.pop('NC_TEST_B')


if __name__ == '__main__':
    unittest.main()
