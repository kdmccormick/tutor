requirements
############

If you want to install a local Python package into the openedx image, then:

1. Move it into this directory.
2. Reboot your platform (``tutor local/k8s/dev reboot``). This will trigger the openedx image to be rebuilt and containers to be recreated.

Going forward, changes to the local package's code should be automatically manifested.

To remove the local package, simply:

1. Move it out of this directory.
2. Reboot your platform (``tutor local/k8s/dev reboot``).

Tip: If you are only testing out a local package with your development environment (``tutor dev``), then you can save image build time by using `../requirements-dev`_ instead.
