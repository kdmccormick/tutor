#!/usr/bin/env python3
from tutor import hooks
from tutor.commands.cli import main
from tutor.plugins.v0 import OfficialPlugin


@hooks.actions.on(hooks.Actions.INSTALL_PLUGINS)
def _install_official_plugins() -> None:
    # Manually install plugins: that's because entrypoint plugins are not properly
    # detected within the binary bundle.
    OfficialPlugin.install_all()


if __name__ == "__main__":
    # Call the regular main function, which will not detect any entrypoint plugin
    main()
