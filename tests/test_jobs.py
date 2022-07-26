import re
import unittest
from io import StringIO
from unittest.mock import patch

from tests.helpers import TestContext, temporary_root
from tutor.types import Config
from tutor import config as tutor_config
from tutor import hooks


class BuiltinJobsTests(unittest.TestCase):
    """
    Test jobs that are defined within core Tutor
    (ie, not plugin-defined jobs).

    TODO: Update these to tests to be more thorough. Currently they
    are essentially just testing that job lookup and script printing are
    working correctly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # TODO: We need to ensure that the CORE_READY signal is fired
        # before running these tests, but is this really the best way to
        # do it?
        hooks.Actions.CORE_READY.do()

    @patch("sys.stdout", new_callable=StringIO)
    def test_initialise(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            runner.run_job("init")
            output = mock_stdout.getvalue().strip()
            self.assertIn("\nService: lms\n", output)
            self.assertIn("\nService: cms\n", output)
            self.assertIn("\nService: mysql\n", output)

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
    def test_create_user(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            runner.run_job(
                "createuser",
                extra_args=(
                    "user1",
                    "user1@example.com",
                    "--staff",
                    "--password",
                    "abc",
                ),
            )

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----\n)(.+)(\n-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "lms")
            self.assertEqual(
                commands.group(2),
                (
                    "sh /openedx/tasks/openedx/lms/createuser "
                    "user1 user1@example.com --staff --password abc"
                ),
            )

    @patch("sys.stdout", new_callable=StringIO)
    def test_import_demo_course(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            runner.run_job("importdemocourse")

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----\n)(.+)(\n-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "cms")
            self.assertEqual(
                commands.group(2), "sh /openedx/tasks/openedx/cms/importdemocourse"
            )

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_theme(self, mock_stdout: StringIO) -> None:
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            runner.run_job(
                "settheme",
                extra_args=("sample_theme", "-d", "domain1", "-d", "domain2"),
            )

            output = mock_stdout.getvalue()
            service = re.search(r"Service: (\w*)", output)
            commands = re.search(r"(-----\n)(.+)(\n-----)", output)
            assert service is not None
            assert commands is not None
            self.assertEqual(service.group(1), "lms")
            self.assertEqual(
                commands.group(2),
                "sh /openedx/tasks/openedx/lms/settheme sample_theme -d domain1 -d domain2",
            )


class LegacyCommandsFiltersTests(unittest.TestCase):
    """
    Ensure that legacy filters COMMANDS_INIT and COMMANDS_PRE_INIT still work.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # TODO: We need to ensure that the CORE_READY signal is fired
        # before running these tests, but is this really the best way to
        # do it?
        hooks.Actions.CORE_READY.do()

    @staticmethod
    def _render_fake_template(_config: Config, *path: str) -> str:
        fake_template_path = "/".join(path)
        return f'echo "Fake template at {fake_template_path}"'

    @patch("sys.stdout", new_callable=StringIO)
    def test_legacy_commands_filters(self, mock_stdout: StringIO) -> None:
        hooks.Filters.COMMANDS_INIT.add_item(("lms", ("path", "to", "init-script")))
        hooks.Filters.COMMANDS_PRE_INIT.add_item(
            ("cms", ("path", "to", "pre-init-script"))
        )
        with temporary_root() as root:
            context = TestContext(root)
            config = tutor_config.load_full(root)
            runner = context.job_runner(config)
            with patch("tutor.jobs.env.render_file", self._render_fake_template):
                runner.run_job("init")
            init_output = (
                "Service: lms\n"
                "-----\n"
                "sh -c 'echo \"Fake template at path/to/init-script\"'\n"
                "-----"
            )
            pre_init_output = (
                "Service: cms\n"
                "-----\n"
                "sh -c 'echo \"Fake template at path/to/pre-init-script\"'\n"
                "-----"
            )
            output = mock_stdout.getvalue()
            self.assertIn(init_output, output)
            self.assertIn(pre_init_output, output)
