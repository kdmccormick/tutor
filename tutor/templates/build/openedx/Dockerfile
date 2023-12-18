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
    xz-utils tk-dev libffi-dev liblzma-dev python-openssl git \
    software-properties-common libmysqlclient-dev libxmlsec1-dev libgeos-dev

ARG PYTHON_VERSION=3.8.15
ENV PYENV_ROOT /opt/pyenv
ENV PATH /openedx/venv/bin:${PATH}
ENV VIRTUAL_ENV /openedx/venv/
ENV XDG_CACHE_HOME /openedx/.cache

# Install pyenv
# https://www.python.org/downloads/
# https://github.com/pyenv/pyenv/releases
ARG PYTHON_VERSION=3.8.18
ENV PYENV_ROOT /opt/pyenv
RUN git clone https://github.com/pyenv/pyenv $PYENV_ROOT --branch v2.3.29 --depth 1

# Install Python
RUN $PYENV_ROOT/bin/pyenv install $PYTHON_VERSION

# Create virtualenv
RUN $PYENV_ROOT/versions/$PYTHON_VERSION/bin/python -m venv /openedx/venv

# Install the right version of pip/setuptools
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
    # https://pypi.org/project/setuptools/
    # https://pypi.org/project/pip/
    # https://pypi.org/project/wheel/
    setuptools==68.2.2 pip==23.2.1. wheel==0.41.2


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
{%- else %}
# Patch edx-platform
{%- endif %}

{# Example: RUN curl -fsSL https://github.com/openedx/edx-platform/commit/<GITSHA1>.patch | git am #}
{{ patch("openedx-dockerfile-post-git-checkout") }}

# TODO: Temporary
# Apply these edx-platform changes which have not yet merged.
RUN curl -fsSL https://github.com/openedx/edx-platform/pull/32835.patch | git am


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
############## LOCALES
############## Download extra locales to /openedx/locale/contrib/locale
###########################################################################################################################
FROM minimal as locales
ARG OPENEDX_I18N_REPOSITORY=https://github.com/openedx/openedx-i18n.git
ARG OPENEDX_I18N_VERSION=release/quince
ADD --keep-git-dir=true $OPENEDX_I18N_REPOSITORY#$OPENEDX_I18N_VERSION /tmp/openedx-i18n
RUN mkdir --parents /openedx/locale && \
    mv /tmp/openedx-i18n/edx-platform/locale /openedx/locale/contrib && \
    rm -rf /tmp/openedx-i18n/


###########################################################################################################################
############## FRONTEND REQUIREMENTS
###########################################################################################################################
FROM python as frontend-requirements

WORKDIR /openedx/edx-platform

# Install python reqs for setting up node & building assets
COPY --link --from=edx-platform /requirements/edx/assets.txt requirements/edx/assets.txt
RUN pip install -r requirements/edx/assets.txt

# Set up node env
ENV PATH /openedx/nodeenv/bin:/openedx/venv/bin:${PATH}
RUN nodeenv /openedx/nodeenv --node=16.14.0 --prebuilt

# Install nodejs requirements
ARG NPM_REGISTRY={{ NPM_REGISTRY }}
COPY --link --from=edx-platform /package.json package.json
COPY --link --from=edx-platform /package-lock.json package-lock.json
COPY --link --from=edx-platform /scripts/copy-node-modules.sh scripts/copy-node-modules.sh
RUN --mount=type=cache,target=/root/.npm,sharing=shared \
    npm clean-install --no-audit --registry=$NPM_REGISTRY

# Set up static root and themes root.
# By default, CMS static root is assumed to be $STUDIO_ROOT_LMS/studio.
ENV STATIC_ROOT_LMS=/openedx/staticfiles
RUN mkdir -p "$STATIC_ROOT_LMS"
ENV EDX_PLATFORM_THEME_DIRS=/openedx/themes
RUN mkdir -p "$EDX_PLATFORM_THEME_DIRS"


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
COPY --link --from=edx-platform --chown=app:app /lms/static/css/vendor lms/static/css/vendor

FROM css as css-production
# Compile default CSS
RUN npm run compile-sass -- --skip-themes
# Compile themed CSS
COPY --link --chown=app:app ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default

FROM css as css-development
# Compile default CSS
RUN npm run compile-sass -- --skip-themes --env=dev
# Compile themed CSS
COPY --link --chown=app:app ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default --env=dev


###########################################################################################################################
############## REQUIREMENTS (frontend+backend)
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
        'django-redis==5.4.0' \
        'uwsgi==2.0.22' \
        'openedx-scorm-xblock>=17.0.0,<18.0.0'

{{ patch("openedx-dockerfile-post-python-requirements") }}

# Install extra Python packages provided by user config.
{% for extra_requirements in OPENEDX_EXTRA_PIP_REQUIREMENTS %}
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install '{{ extra_requirements }}'
{% endfor %}

FROM requirements as requirements-production

# Remove everything related to libsass (which is installed via assets.txt) in order to shrink the final prod image.
# This is safe because we don't need to compile Sass in production.
# Now, what we *could* have done was base this stage on minimal, thus avoiding assets.txt altogether.
# However, this would mean that we'd have to install libsass *twice*: once for frontend-requirements and
# once for requirements. Since libsass takes so long to compile, that doesn't seem worth it.
RUN rm -r /openedx/venv/lib/python3.8/site-packages/*sass*

# Install auto-mounted directories as Python packages.
{% for name in iter_mounted_directories(MOUNTS, "openedx") %}
COPY --from=mnt-{{ name }} --chown=app:app / /mnt/{{ name }}
RUN pip install -e "/mnt/{{ name }}"
{% endfor %}

FROM requirements as requirements-development

# Install edx-platform's dev requirements, plus ipdb and ipython for an improved debugging experience.
COPY --link --from=edx-platform /requirements/edx/development.txt /openedx/edx-platform/requirements/edx/development.txt
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        -r /openedx/edx-platform/requirements/edx/development.txt \
        ipdb==0.13.13 \
        ipython==8.12.3

# Install auto-mounted directories as Python packages.
# This must be done after installing development.txt, otherwise the pins in development.txt would
# supersede the auto-mounted packages.
{% for name in iter_mounted_directories(MOUNTS, "openedx-dev") %}
COPY --from=mnt-{{ name }} --chown=app:app / /mnt/{{ name }}
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

# From then on, run as unprivileged "app" user
# Note that this must always be different from root (APP_USER_ID=0)
ARG APP_USER_ID=1000
RUN if [ "$APP_USER_ID" = 0 ]; then echo "app user may not be root" && false; fi
RUN useradd --no-log-init --home-dir /openedx --create-home --shell /bin/bash --uid ${APP_USER_ID} app
USER ${APP_USER_ID}

# Copy in backend code and requirements.
# Dockerize tags: https://hub.docker.com/r/powerman/dockerize/tags
COPY --link --from=docker.io/powerman/dockerize:0.19.0 /usr/local/bin/dockerize /usr/local/bin/dockerize
COPY --link --chown=app:app --from=edx-platform / /openedx/edx-platform
COPY --link --chown=app:app ./themes/ /openedx/themes/
COPY --link --chown=app:app --from=locales /openedx/locale /openedx/locale
COPY --link --chown=app:app --from=python /opt/pyenv /opt/pyenv
COPY --link --chown=app:app --from=requirements-production /openedx/venv /openedx/venv
COPY --link --chown=app:app --from=requirements-production /mnt /mnt

ENV PATH /openedx/venv/bin:./node_modules/.bin:/openedx/nodeenv/bin:${PATH}
ENV VIRTUAL_ENV /openedx/venv/
WORKDIR /openedx/edx-platform

# Install the local edx-platform repo. This:
# (1) creates an egg-info folder which is necessary to enable entrypoints like XBlocks, and
# (2) points the virtualenv at the local edx-platform repo.
RUN pip install -e .

# Create folder that will store lms/cms.env.yml files, as well as
# the tutor-specific settings files.
RUN mkdir -p /openedx/config ./lms/envs/tutor ./cms/envs/tutor
COPY --chown=app:app revisions.yml /openedx/config/
ENV LMS_CFG /openedx/config/lms.env.yml
ENV CMS_CFG /openedx/config/cms.env.yml
ENV REVISION_CFG /openedx/config/revisions.yml
COPY --chown=app:app settings/lms/*.py ./lms/envs/tutor/
COPY --chown=app:app settings/cms/*.py ./cms/envs/tutor/

# Copy user-specific locales to /openedx/locale/user/locale and compile them
RUN mkdir /openedx/locale/user
COPY --chown=app:app ./locale/ /openedx/locale/user/locale/
RUN cd /openedx/locale/user && \
    django-admin compilemessages -v1

# Copy in frontend requirements.
COPY --link --chown=app:app --from=frontend-requirements \
	/openedx/nodeenv \
	/openedx/nodeenv
COPY --link --chown=app:app --from=frontend-requirements \
	/openedx/edx-platform/node_modules \
	/openedx/edx-platform/node_modules
COPY --link --chown=app:app --from=frontend-requirements \
   /openedx/edx-platform/common/static/common/js/vendor \
   /openedx/edx-platform/common/static/common/js/vendor
COPY --link --chown=app:app --from=frontend-requirements \
	/openedx/edx-platform/common/static/common/css/vendor \
	/openedx/edx-platform/common/static/common/css/vendor

# Compile i18n strings: in some cases, js locales are not properly compiled out of the box
# and we need to do a pass ourselves. Also, we need to compile the djangojs.js files for
# the downloaded locales.
RUN ./manage.py lms --settings=tutor.i18n compilejsi18n
RUN ./manage.py cms --settings=tutor.i18n compilejsi18n

# Copy scripts
COPY --link --chown=app:app ./bin /openedx/bin
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
FROM application as production

# Copy in and collect production static assets.
COPY --link --chown=app:app --from=bundles-production /openedx/staticfiles /openedx/staticfiles
COPY --link --chown=app:app --from=bundles-production /openedx/edx-platform/common/static/bundles common/static/bundles
COPY --link --chown=app:app --from=css-production /openedx/edx-platform/lms/static/css lms/static/css
COPY --link --chown=app:app --from=css-production /openedx/edx-platform/lms/static/certificates/css lms/static/certificates/css
COPY --link --chown=app:app --from=css-production /openedx/edx-platform/cms/static/css cms/static/css
RUN ./manage.py lms collectstatic --noinput --settings=tutor.assets
RUN ./manage.py cms collectstatic --noinput --settings=tutor.assets

# De-dupe static assets with synlinks
RUN rdfind -makesymlinks true -followsymlinks true /openedx/staticfiles/

# Default amount of uWSGI processes
ENV UWSGI_WORKERS=2

# Copy the default uWSGI configuration
COPY --chown=app:app settings/uwsgi.ini .

# Default django settings
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.production

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
# (This forces us to re-install the local edx-platform repo as well.)
COPY --link --chown=app:app --from=requirements-development /openedx/venv /openedx/venv
COPY --link --chown=app:app --from=requirements-development /mnt /mnt
RUN pip install -e .

# Add ipdb as default PYTHONBREAKPOINT
ENV PYTHONBREAKPOINT=ipdb.set_trace

# Copy in development static assets.
# In development mode, edx-platform expects the files to be in the repo, and pointed to by webpack-stats.json.
COPY --link --chown=app:app --from=bundles-development /openedx/staticfiles/webpack-stats.json /openedx/staticfiles/webpack-stats.json
COPY --link --chown=app:app --from=bundles-development /openedx/staticfiles/studio/webpack-stats.json /openedx/staticfiles/studio/webpack-stats.json
COPY --link --chown=app:app --from=bundles-development /openedx/edx-platform/common/static/bundles common/static/bundles
COPY --link --chown=app:app --from=css-development /openedx/edx-platform/lms/static/css lms/static/css
COPY --link --chown=app:app --from=css-development /openedx/edx-platform/lms/static/certificates/css lms/static/certificates/css
COPY --link --chown=app:app --from=css-development /openedx/edx-platform/cms/static/css cms/static/css

{{ patch("openedx-dev-dockerfile-post-python-requirements") }}

# Default django settings
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.development

CMD ./manage.py $SERVICE_VARIANT runserver 0.0.0.0:8000
