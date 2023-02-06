requirements-dev
################

If you want to install a local Python package into the openedx-dev image, then:

1. Move it into this directory.
2. Reboot your development platform (``tutor dev reboot``). This will trigger the openedx-dev image to be rebuilt and containers to be recreated.

Going forward, changes to the local package's code should be automatically manifested.

To remove the local package, simply:

1. Move it out of this directory.
2. Reboot your development platform (``tutor dev reboot``).

Please note: This strategy will only affect the image for the Open edX development (``tutor dev``) environment. To install a package into all environments (``tutor dev``, ``tutor local``, ``tutor k8s``), use the `../requirements`_ directory instead.

