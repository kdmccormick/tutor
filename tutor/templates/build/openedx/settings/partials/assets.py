"""
Bare minimum settings for collecting production assets.
"""
from ..common import *
from openedx.core.lib.derived import derive_settings

ENABLE_COMPREHENSIVE_THEMING = True
COMPREHENSIVE_THEME_DIRS.append('/openedx/themes')

STATIC_ROOT_BASE = '/openedx/staticfiles'

SECRET_KEY = 'secret'
XQUEUE_INTERFACE = {
    'django_auth': None,
    'url': None,
}
DATABASES = {
    "default": {},
}

# Upstream expects node_modules to be within edx-platform, but we put
# node_modules under /openedx/node_modules, so we must adjust any settings
# that hold a node_modules path.
NODE_MODULES_ROOT = "/openedx/node_modules/@edx"
STATICFILES_DIRS = [
    *[
        staticfiles_dir for staticfiles_dir in STATICFILES_DIRS
        if "node_modules/@edx" not in staticfiles_dir
    ],
    NODE_MODULES_ROOT,
]
PIPELINE["UGLIFYJS_BINARY"] = "/openedx/node_modules/.bin/uglifyjs"

{{ patch("openedx-common-assets-settings") }}
