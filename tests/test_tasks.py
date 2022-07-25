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

    # TODO: Update these tests so they work on new 'do init' task.
    # @patch("sys.stdout", new_callable=StringIO)
    # def test_initialise(self, mock_stdout: StringIO) -> None:
    #     with temporary_root() as root:
    #         context = TestContext(root)
    #         config = tutor_config.load_full(root)
    #         runner = context.job_runner(config)
    #         jobs.initialise(runner)
    #         output = mock_stdout.getvalue().strip()
    #         self.assertTrue(output.startswith("Initialising all services..."))
    #         self.assertTrue(output.endswith("All services initialised."))

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

    # TODO: Update these tests so they work on new 'do createuser' task.
    # def test_create_user_without_staff(self) -> None:
    #    command = jobs.create_user_command("superuser", False, "username", "email")
    #    self.assertNotIn("--staff", command)

    # def test_create_user_with_staff(self) -> None:
    #    command = jobs.create_user_command("superuser", True, "username", "email")
    #    self.assertIn("--staff", command)

    # def test_create_user_with_staff_with_password(self) -> None:
    #    command = jobs.create_user_command(
    #        "superuser", True, "username", "email", "command"
    #    )
    #    self.assertIn("set_password", command)

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_theme(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            run_task(
                runner,
                "settheme",
                args=["sample_theme", "-d", "domain1", "-d", "domain2"],
            )

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----)([\S\s]+)(-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "lms")
            self.assertTrue(
                commands.group(2)
                .strip()
                .startswith('sh -c \'theme=""\ndomains=""\nusage="')
            )
