import re
import unittest
from io import StringIO
from unittest.mock import patch

from tests.helpers import TestContext, temporary_root
from tutor import config as tutor_config
from tutor import jobs


class JobsTests(unittest.TestCase):
    @patch("sys.stdout", new_callable=StringIO)
    def test_initialise(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            jobs.initialise(runner)
            output = mock_stdout.getvalue().strip()
            self.assertTrue(output.startswith("Initialising all services..."))
            self.assertTrue(output.endswith("All services initialised."))

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_theme(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            jobs.set_theme("sample_theme", ["domain1", "domain2"], runner)

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----)([\S\s]+)(-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "lms")
            self.assertTrue(
                commands.group(2)
                .strip()
                .startswith('echo "Loading settings $DJANGO_SETTINGS_MODULE"')
            )

    def test_get_all_openedx_domains(self) -> None:
        with temporary_root() as root:
            config = tutor_config.load_full(root)
            domains = jobs.get_all_openedx_domains(config)
            self.assertTrue(domains)
            self.assertEqual(6, len(domains))
