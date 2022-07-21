import re
import unittest
from io import StringIO
from unittest.mock import patch

from tests.helpers import TestContext, temporary_root
from tutor import config as tutor_config
from tutor.commands.tasks import run_task


class BuiltinTaskTests(unittest.TestCase):
    """
    Test tasks that are defined within core Tutor
    (ie, not plugin-defined tasks).
    """

    @patch("sys.stdout", new_callable=StringIO)
    def test_import_demo_course(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            run_task(runner, "importdemocourse")

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----)([\S\s]+)(-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "cms")
            self.assertTrue(
                commands.group(2)
                .strip()
                .startswith('sh -c \'echo "Loading settings $DJANGO_SETTINGS_MODULE"')
            )
