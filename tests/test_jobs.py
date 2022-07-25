import unittest

from tests.helpers import temporary_root
from tutor import config as tutor_config
from tutor import jobs


class JobsTests(unittest.TestCase):
    def test_get_all_openedx_domains(self) -> None:
        with temporary_root() as root:
            config = tutor_config.load_full(root)
            domains = jobs.get_all_openedx_domains(config)
            self.assertTrue(domains)
            self.assertEqual(6, len(domains))
