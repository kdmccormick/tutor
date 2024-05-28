# syntax=docker/dockerfile:1


###########################################################################################################################
############## MINIMAL
############## Minimal image with base system requirements for most stages
###########################################################################################################################
FROM docker.io/ubuntu:20.04 as minimal
LABEL maintainer="Overhang.io <contact@overhang.io>"

ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install -y build-essential curl git language-pack-en
ENV LC_ALL en_US.UTF-8
{{ patch("openedx-dockerfile-minimal") }}

ARG PYTHON_VERSION=3.11.8
ENV PATH /openedx/venv/bin:./node_modules/.bin:/openedx/nodeenv/bin:${PATH}
ENV PYENV_ROOT /opt/pyenv
ENV VIRTUAL_ENV /openedx/venv/
ENV XDG_CACHE_HOME /openedx/.cache
ENV COMPREHENSIVE_THEME_DIRS /openedx/themes
ENV STATIC_ROOT_LMS /openedx/staticfiles
ENV STATIC_ROOT_CMS /openedx/staticfiles/studio


###########################################################################################################################
############## PYTHON
############## Install python with pyenv in /opt/pyenv and create virtualenv in /openedx/venv
###########################################################################################################################
FROM minimal as python

# https://github.com/pyenv/pyenv/wiki/Common-build-problems#prerequisites
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install -y libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
    xz-utils tk-dev libffi-dev liblzma-dev python-openssl git

# Install pyenv (https://github.com/pyenv/pyenv/releases)
RUN git clone https://github.com/pyenv/pyenv $PYENV_ROOT --branch v2.3.36 --depth 1

# Install Python (https://www.python.org/downloads/)
RUN $PYENV_ROOT/bin/pyenv install $PYTHON_VERSION

# Create virtualenv
RUN $PYENV_ROOT/versions/$PYTHON_VERSION/bin/python -m venv /openedx/venv

# Install the right version of pip/setuptools/wheel
#    https://pypi.org/project/setuptools/
#    https://pypi.org/project/pip/
#    https://pypi.org/project/wheel/
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
    setuptools==69.1.1 pip==24.0 wheel==0.43.0


###########################################################################################################################
############## CODE
###########################################################################################################################
FROM minimal as code

###### Checkout edx-platform code
ARG EDX_PLATFORM_REPOSITORY={{ EDX_PLATFORM_REPOSITORY }}
ARG EDX_PLATFORM_VERSION={{ EDX_PLATFORM_VERSION }}
RUN mkdir -p /openedx/edx-platform && \
    git clone $EDX_PLATFORM_REPOSITORY --branch $EDX_PLATFORM_VERSION --depth 1 /openedx/edx-platform
WORKDIR /openedx/edx-platform

# Identify tutor user to apply patches using git
RUN git config --global user.email "tutor@overhang.io" \
  && git config --global user.name "Tutor"

{%- if patch("openedx-dockerfile-git-patches-default") %}
# Custom edx-platform patches
{{ patch("openedx-dockerfile-git-patches-default") }}
{%- elif EDX_PLATFORM_VERSION == "master" %}
# Patches in nightly node
{%- else %}
# Patches in non-nightly mode
# Prevent course structure cache infinite growth
# https://github.com/openedx/edx-platform/pull/34210
RUN curl -fsSL https://github.com/openedx/edx-platform/commit/ad201cd664b6c722cbefcbda23ae390c06daf621.patch | git am
# Security patch for "Privilege re-escalation in Studio after staff access removed"
# https://github.com/openedx/edx-platform/security/advisories/GHSA-99vw-2wrq-xh9x
# https://discuss.openedx.org/t/upcoming-security-fix-for-edx-platform-on-2024-05-17/13004
RUN curl -fsSL https://github.com/openedx/edx-platform/commit/3ff69fd5813256f935f19c237ea0c42d4c16edbf.patch | git am
{%- endif %}

{# Example: RUN curl -fsSL https://github.com/openedx/edx-platform/commit/<GITSHA1>.patch | git am #}
{{ patch("openedx-dockerfile-post-git-checkout") }}


###########################################################################################################################
############## EDX-PLATFORM
############## Empty layer with just the repo at the root.
############## This is useful when overriding the build context with a host repo:
############## docker build --build-context edx-platform=/path/to/edx-platform
###########################################################################################################################
FROM scratch as edx-platform
COPY --from=code /openedx/edx-platform /


###########################################################################################################################
############## MNT-*
############## Create an empty layer for each bind-mounted directory relevant to our image.
###########################################################################################################################
{% for name in iter_mounted_directories(MOUNTS, "openedx") %}
FROM scratch as mnt-{{ name }}
{% endfor %}


###########################################################################################################################
############## FRONTEND REQUIREMENTS
###########################################################################################################################
FROM python as frontend-requirements

WORKDIR /openedx/edx-platform

# Install python reqs for setting up node & building assets
COPY --from=edx-platform /requirements/edx/assets.txt requirements/edx/assets.txt
RUN pip install -r requirements/edx/assets.txt

# Set up node env
ENV PATH /openedx/nodeenv/bin:/openedx/venv/bin:${PATH}
RUN nodeenv /openedx/nodeenv --node=18.20.1 --prebuilt

# Install nodejs requirements
ARG NPM_REGISTRY={{ NPM_REGISTRY }}
COPY --from=edx-platform /package.json package.json
COPY --from=edx-platform /package-lock.json package-lock.json
COPY --from=edx-platform /scripts/copy-node-modules.sh scripts/copy-node-modules.sh
RUN --mount=type=cache,target=/root/.npm,sharing=shared \
    npm clean-install --no-audit --registry=$NPM_REGISTRY


###########################################################################################################################
############## BUNDLES
###########################################################################################################################

FROM frontend-requirements as bundles

COPY --link --from=edx-platform /.babelrc .babelrc
COPY --link --from=edx-platform /webpack-config/file-lists.js webpack-config/file-lists.js
COPY --link --from=edx-platform /webpack.builtinblocks.config.js webpack.builtinblocks.config.js
COPY --link --from=edx-platform /webpack.common.config.js webpack.common.config.js
COPY --link --from=edx-platform /webpack.dev.config.js webpack.dev.config.js
COPY --link --from=edx-platform /webpack.prod.config.js webpack.prod.config.js
COPY --link --from=edx-platform /cms/djangoapps/pipeline_js/js cms/djangoapps/pipeline_js/js
COPY --link --from=edx-platform /cms/static cms/static
COPY --link --from=edx-platform /cms/templates/ cms/templates/
COPY --link --from=edx-platform /common/static/common common/static/common
COPY --link --from=edx-platform /common/static/js/ common/static/js
COPY --link --from=edx-platform /lms/djangoapps/discussion/static lms/djangoapps/discussion/static
COPY --link --from=edx-platform /lms/djangoapps/instructor/static lms/djangoapps/instructor/static
COPY --link --from=edx-platform /lms/djangoapps/support/static/support lms/djangoapps/support/static/support
COPY --link --from=edx-platform /lms/djangoapps/teams/static lms/djangoapps/teams/static
COPY --link --from=edx-platform /lms/static/ lms/static/
COPY --link --from=edx-platform /lms/templates/ lms/templates/
COPY --link --from=edx-platform /openedx/features/announcements/static openedx/features/announcements/static
COPY --link --from=edx-platform /openedx/features/course_bookmarks/static openedx/features/course_bookmarks/static
COPY --link --from=edx-platform /openedx/features/course_experience/static openedx/features/course_experience/static
COPY --link --from=edx-platform /openedx/features/course_search/static openedx/features/course_search/static
COPY --link --from=edx-platform /openedx/features/learner_profile/static openedx/features/learner_profile/static
COPY --link --from=edx-platform /xmodule/assets xmodule/assets
COPY --link --from=edx-platform /xmodule/js xmodule/js

COPY --link --from=frontend-requirements /openedx/edx-platform/common/static/common/js/vendor common/static/common/js/vendor
COPY --link --from=frontend-requirements /openedx/edx-platform/common/static/common/css/vendor common/static/common/css/vendor

FROM bundles as bundles-production
RUN npm run webpack

FROM bundles as bundles-development
RUN npm run webpack-dev


###########################################################################################################################
############## CSS
###########################################################################################################################

FROM frontend-requirements as css

ENV PATH ./node_modules/.bin:${PATH}

COPY --link --from=edx-platform /scripts/compile_sass.py scripts/compile_sass.py
COPY --link --from=edx-platform /common/static common/static
COPY --link --from=edx-platform /lms/static/sass lms/static/sass
COPY --link --from=edx-platform /lms/static/sass/partials lms/static/sass/partials
COPY --link --from=edx-platform /lms/static/certificates/sass lms/static/certificates/sass
COPY --link --from=edx-platform /cms/static/sass cms/static/sass
COPY --link --from=edx-platform /cms/static/sass/partials cms/static/sass/partials
COPY --link --from=edx-platform /xmodule/assets xmodule/assets
COPY --link --from=edx-platform /lms/static/css/vendor lms/static/css/vendor

FROM css as css-production
RUN npm run compile-sass -- --skip-themes
COPY --link ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default

FROM css as css-development
RUN npm run compile-sass -- --skip-themes --env=dev
COPY --link ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default --env=dev


###########################################################################################################################
############## FULL REQUIREMENTS
###########################################################################################################################

# Start with frontend requirements already installed.
FROM frontend-requirements as requirements

# Install:
# * base Python packages from edx-platform,
# * Redis as a django cache (https://pypi.org/project/django-redis/),
# * the uWSGI server (https://pypi.org/project/uWSGI/),
# * and the SCORM XBlock.
COPY --link --from=edx-platform /requirements/edx/base.txt /openedx/edx-platform/requirements/edx/base.txt
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        -r /openedx/edx-platform/requirements/edx/base.txt \
        django-redis==5.4.0 \
        uwsgi==2.0.24 \
        'openedx-scorm-xblock>=17.0.0,<18.0.0'

{{ patch("openedx-dockerfile-post-python-requirements") }}

# Install extra Python packages provided by user config.
{% for extra_requirements in OPENEDX_EXTRA_PIP_REQUIREMENTS %}
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install '{{ extra_requirements }}'
{% endfor %}

FROM requirements as requirements-production

# Install auto-mounted directories as Python packages.
{% for name in iter_mounted_directories(MOUNTS, "openedx") %}
COPY --link --from=mnt-{{ name }} / /mnt/{{ name }}
RUN pip install -e "/mnt/{{ name }}"
{% endfor %}

FROM requirements as requirements-development

# Install edx-platform's dev requirements, plus ipdb and ipython for an improved debugging experience.
#   https://pypi.org/project/ipdb/
#   https://pypi.org/project/ipython (>=Python 3.10 started with 8.20)
COPY --link --from=edx-platform /requirements/edx/development.txt /openedx/edx-platform/requirements/edx/development.txt
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        -r /openedx/edx-platform/requirements/edx/development.txt \
        ipdb==0.13.13 \
        ipython==8.24.0

# Install auto-mounted directories as Python packages.
# This must be done after installing development.txt, otherwise the pins in development.txt would
# supersede the auto-mounted packages.
{% for name in iter_mounted_directories(MOUNTS, "openedx-dev") %}
COPY --link --from=mnt-{{ name }} / /mnt/{{ name }}
RUN pip install -e "/mnt/{{ name }}"
{% endfor %}


###########################################################################################################################
############## APPLICATION (base for final production and development images)
###########################################################################################################################
FROM minimal as application

# Install system requirements
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update \
    && apt install -y gettext gfortran graphviz graphviz-dev libffi-dev libfreetype6-dev libgeos-dev libjpeg8-dev liblapack-dev libmysqlclient-dev libpng-dev libsqlite3-dev libxmlsec1-dev lynx mysql-client ntp pkg-config rdfind

# From then on, run as unprivileged "app" user.
# Note that this must always be different from root (APP_USER_ID=0).
# Note that we must now chown any files that we COPY 
ARG APP_USER_ID=1000
RUN if [ "$APP_USER_ID" = 0 ]; then echo "app user may not be root" && false; fi
RUN useradd --no-log-init --home-dir /openedx --create-home --shell /bin/bash --uid ${APP_USER_ID} app
USER ${APP_USER_ID}

# Going forward, as we COPY files into the application image, we must chown anything that the app user may write to.
# We chown with the integer APP_USER_ID rather than the 'app' username because the '--link' optimization flag tells
# COPY to disregard filesystem changes from previous layers, including the systems' username <-> userid mapping file.

# Dockerize tags: https://hub.docker.com/r/powerman/dockerize/tags
COPY --link --from=docker.io/powerman/dockerize:0.19.0 /usr/local/bin/dockerize /usr/local/bin/dockerize

# Copy in pyenv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=python /opt/pyenv /opt/pyenv

# Copy in backend code
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=edx-platform / /openedx/edx-platform

# Copy in frontend requirements.
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=frontend-requirements \
    /openedx/nodeenv \
    /openedx/nodeenv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=frontend-requirements \
    /openedx/edx-platform/node_modules \
    /openedx/edx-platform/node_modules
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=frontend-requirements \
   /openedx/edx-platform/common/static/common/js/vendor \
   /openedx/edx-platform/common/static/common/js/vendor
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=frontend-requirements \
    /openedx/edx-platform/common/static/common/css/vendor \
    /openedx/edx-platform/common/static/common/css/vendor

# Work out of edx-platform repo from here on out.
WORKDIR /openedx/edx-platform

# Create folder that will store lms/cms.env.yml files, as well as
# the tutor-specific settings files.
RUN mkdir -p /openedx/config ./lms/envs/tutor ./cms/envs/tutor
COPY --link revisions.yml /openedx/config/
ENV LMS_CFG /openedx/config/lms.env.yml
ENV CMS_CFG /openedx/config/cms.env.yml
ENV REVISION_CFG /openedx/config/revisions.yml
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/lms/*.py ./lms/envs/tutor/
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/cms/*.py ./cms/envs/tutor/

# Copy scripts
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} ./bin /openedx/bin
RUN chmod a+x /openedx/bin/*
ENV PATH /openedx/bin:${PATH}

# Create a data directory, which might be used (or not)
RUN mkdir /openedx/data

# service variant is "lms" or "cms"
ENV SERVICE_VARIANT lms

{{ patch("openedx-dockerfile") }}

EXPOSE 8000


###########################################################################################################################
############## PRODUCTION
###########################################################################################################################

FROM application as application-plus-production-requirements
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=requirements-production /openedx/venv /openedx/venv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=requirements-production /mnt /mnt
RUN pip install -e .

FROM application-plus-production-requirements as locales
RUN make clean_translations
RUN ./manage.py lms --settings=tutor.i18n pull_plugin_translations --verbose --repository='{{ ATLAS_REPOSITORY }}' --revision='{{ ATLAS_REVISION }}' {{ ATLAS_OPTIONS }}
RUN ./manage.py lms --settings=tutor.i18n pull_xblock_translations --repository='{{ ATLAS_REPOSITORY }}' --revision='{{ ATLAS_REVISION }}' {{ ATLAS_OPTIONS }}
RUN atlas pull --repository='{{ ATLAS_REPOSITORY }}' --revision='{{ ATLAS_REVISION }}' {{ ATLAS_OPTIONS }} \
    translations/edx-platform/conf/locale:conf/locale \
    translations/studio-frontend/src/i18n/messages:conf/plugins-locale/studio-frontend
RUN ./manage.py lms --settings=tutor.i18n compile_xblock_translations
RUN ./manage.py cms --settings=tutor.i18n compile_xblock_translations
RUN ./manage.py lms --settings=tutor.i18n compile_plugin_translations
RUN ./manage.py lms --settings=tutor.i18n compilemessages -v1
RUN ./manage.py lms --settings=tutor.i18n compilejsi18n
RUN ./manage.py cms --settings=tutor.i18n compilejsi18n

FROM application-plus-production-requirements as production

# Copy in locales
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=locales \
	/openedx/edx-platform/conf/locale \
	/openedx/edx-platform/conf/locale
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=locales \
	/openedx/edx-platform/conf/plugins-locale \
	/openedx/edx-platform/conf/plugins-locale

# Copy in and collect production static assets.
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=bundles-production \
	/openedx/staticfiles \
	/openedx/staticfiles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=bundles-production \
	/openedx/edx-platform/common/static/bundles \
	common/static/bundles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-production \
	/openedx/edx-platform/lms/static/css \
	lms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-production \
	/openedx/edx-platform/lms/static/certificates/css \
	lms/static/certificates/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-production \
	/openedx/edx-platform/cms/static/css \
	cms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-production \
	/openedx/themes \
	/openedx/themes
RUN ./manage.py lms collectstatic --noinput --settings=tutor.assets
RUN ./manage.py cms collectstatic --noinput --settings=tutor.assets

# De-dupe static assets with synlinks
RUN rdfind -makesymlinks true -followsymlinks true /openedx/staticfiles/

# Copy the default uWSGI configuration
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/uwsgi.ini .

# Default django settings
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.production

# Default amount of uWSGI processes
ENV UWSGI_WORKERS=2

# Run server
CMD uwsgi uwsgi.ini

{{ patch("openedx-dockerfile-final") }}


###########################################################################################################################
############## DEVELOPMENT
###########################################################################################################################
FROM application as development

# Install useful system requirements (as root)
USER root
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install -y vim iputils-ping dnsutils telnet
USER app

# Copy in dev python requirements.
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=requirements-development /openedx/venv /openedx/venv
RUN pip install -e .

{{ patch("openedx-dev-dockerfile-post-python-requirements") }}

# Add ipdb as default PYTHONBREAKPOINT
ENV PYTHONBREAKPOINT=ipdb.set_trace

# In development mode, edx-platform expects the files to be in the repo, and pointed to by webpack-stats.json.
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=bundles-development \
	/openedx/staticfiles/webpack-stats.json \
	/openedx/staticfiles/webpack-stats.json
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=bundles-development \
	/openedx/staticfiles/studio/webpack-stats.json \
	/openedx/staticfiles/studio/webpack-stats.json
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=bundles-development \
	/openedx/edx-platform/common/static/bundles \
	common/static/bundles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-development \
	/openedx/edx-platform/lms/static/css \
	lms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-development \
	/openedx/edx-platform/lms/static/certificates/css \
	lms/static/certificates/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-development \
	/openedx/edx-platform/cms/static/css \
	cms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-development \
	/openedx/themes \
	/openedx/themes

# Default django settings
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.development

CMD ./manage.py $SERVICE_VARIANT runserver 0.0.0.0:8000
