#############################################################################
###### Minimal image with base system requirements for most stages

FROM docker.io/ubuntu:20.04 as minimal
LABEL maintainer="Overhang.io <contact@overhang.io>"

ENV DEBIAN_FRONTEND=noninteractive
# TODO: Safe/effective to rm var/lib/apt/lists in all these places?
RUN apt update && \
    apt install -y \
	  build-essential \
	  curl \
	  language-pack-en \
	  git \
	  && \
	rm -rf /var/lib/apt/lists/*
ENV LC_ALL en_US.UTF-8

{{ patch("openedx-dockerfile-minimal") }}

#############################################################################
###### Python with pyenv in /opt/pyenv and create virtualenv in /openedx/venv

FROM minimal as python

# https://github.com/pyenv/pyenv/wiki/Common-build-problems#prerequisites
RUN apt update && \
    apt install -y \
	  curl \
	  git \
	  libbz2-dev \
	  libffi-dev \
	  liblzma-dev \
	  libncurses5-dev \
	  libncursesw5-dev \
      libreadline-dev \
	  libsqlite3-dev \
	  libssl-dev \
	  llvm \
	  python-openssl \
	  tk-dev \
	  wget \
      xz-utils \
	  zlib1g-dev \
	  && \
	rm -rf /var/lib/apt/lists/*
ARG PYTHON_VERSION=3.8.12
ENV PYENV_ROOT /opt/pyenv
RUN git clone https://github.com/pyenv/pyenv $PYENV_ROOT --branch v2.2.2 --depth 1
RUN $PYENV_ROOT/bin/pyenv install $PYTHON_VERSION
RUN $PYENV_ROOT/versions/$PYTHON_VERSION/bin/python -m venv /openedx/venv

#############################################################################
###### Dockerize stage to wait for mysql DB availability

FROM minimal as dockerize
# https://github.com/powerman/dockerize/releases
ARG DOCKERIZE_VERSION=v0.16.0
RUN dockerize_url="https://github.com/powerman/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-$(uname -m | sed 's@aarch@arm@')" \
    && echo "Downloading dockerize from $dockerize_url" \
    && curl --fail --location --output /usr/local/bin/dockerize $dockerize_url \
    && chmod a+x /usr/local/bin/dockerize

#############################################################################
###### Clone edx-platform in an intermediate stage

FROM minimal as code
ARG EDX_PLATFORM_REPOSITORY={{ EDX_PLATFORM_REPOSITORY }}
ARG EDX_PLATFORM_VERSION={{ EDX_PLATFORM_VERSION }}
RUN echo BREAK CACHE 1
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

{# Example: RUN curl -fsSL https://github.com/openedx/edx-platform/commit/<GITSHA1> | git am #}
{{ patch("openedx-dockerfile-post-git-checkout") }}

#############################################################################
###### Download extra locales to /openedx/locale/contrib/locale

FROM minimal as locales
ARG OPENEDX_I18N_VERSION={{ OPENEDX_COMMON_VERSION }}
RUN cd /tmp \
    && curl -L -o openedx-i18n.tar.gz https://github.com/openedx/openedx-i18n/archive/$OPENEDX_I18N_VERSION.tar.gz \
    && tar xzf /tmp/openedx-i18n.tar.gz \
    && mkdir -p /openedx/locale/contrib \
    && mv openedx-i18n-*/edx-platform/locale /openedx/locale/contrib \
    && rm -rf openedx-i18n*

#############################################################################
###### Install python requirements in virtualenv

FROM python as python-requirements
ENV PATH /openedx/venv/bin:${PATH}
ENV VIRTUAL_ENV /openedx/venv/

# TODO: Why are these here instead of an earlier stage?
RUN apt update && \
    apt install -y \
	  software-properties-common \
	  libmysqlclient-dev \
	  libxmlsec1-dev \
	  libgeos-dev \
      && \
    rm -rf /var/lib/apt/lists/*

# Install the right version of pip/setuptools
# https://pypi.org/project/setuptools/
# https://pypi.org/project/pip/
# https://pypi.org/project/wheel/
RUN pip install setuptools==62.1.0 pip==22.0.4 wheel==0.37.1


# Install django-redis for using redis as a django cache
# https://pypi.org/project/django-redis/
RUN pip install django-redis==5.2.0

# Install uwsgi
# https://pypi.org/project/uWSGI/
RUN pip install uwsgi==2.0.20

# Install base requirements
COPY --from=code /openedx/edx-platform/requirements/edx/base.txt /openedx/edx-platform/requirements/edx/base.txt
WORKDIR /openedx/edx-platform
RUN pip install -r ./requirements/edx/base.txt

{{ patch("openedx-dockerfile-post-python-requirements") }}

# Install private requirements: this is useful for installing custom xblocks.
COPY ./requirements/ /openedx/requirements
RUN cd /openedx/requirements/ \
  && touch ./private.txt \
  && pip install -r ./private.txt

{% for extra_requirements in OPENEDX_EXTRA_PIP_REQUIREMENTS %}RUN pip install '{{ extra_requirements }}'
{% endfor %}

#############################################################################
###### Install nodejs with nodeenv in /openedx/nodeenv

FROM python as nodejs-requirements
ENV PATH /openedx/nodeenv/bin:/openedx/venv/bin:${PATH}

# Install nodeenv with the version provided by edx-platform
RUN pip install nodeenv==1.6.0
RUN nodeenv /openedx/nodeenv --node=16.14.0 --prebuilt

# Install nodejs requirements
ARG NPM_REGISTRY={{ NPM_REGISTRY }}
COPY --from=code /openedx/edx-platform/package.json /openedx/edx-platform/package.json
COPY --from=code /openedx/edx-platform/package-lock.json /openedx/edx-platform/package-lock.json
WORKDIR /openedx/edx-platform
RUN npm install --verbose --registry=$NPM_REGISTRY

#############################################################################
###### Production image with system and python requirements

FROM minimal as production

# Install system requirements
RUN apt update && \
    apt install -y \
	  gettext \
	  gfortran \
	  graphviz \
	  graphviz-dev \
	  libffi-dev \
	  libfreetype6-dev \
	  libgeos-dev \
	  libjpeg8-dev \
	  liblapack-dev \
	  libmysqlclient-dev \
	  libpng-dev \
	  libsqlite3-dev \
	  libxmlsec1-dev \
	  lynx \
	  ntp \
	  pkg-config \
	  rdfind \
	  && \
    rm -rf /var/lib/apt/lists/*

# From here on, run as unprivileged "app" user
# Note that this must always be different from root (APP_USER_ID=0)
ARG APP_USER_ID=1000
RUN if [ "$APP_USER_ID" = 0 ]; then echo "app user may not be root" && false; fi
RUN useradd --home-dir /openedx --create-home --shell /bin/bash --uid ${APP_USER_ID} app
USER ${APP_USER_ID}

# Copy in everything we need from the intermediate build stages
COPY                 --from=dockerize /usr/local/bin/dockerize /usr/local/bin/dockerize
COPY --chown=app:app --from=code /openedx/edx-platform /openedx/edx-platform
COPY --chown=app:app --from=locales /openedx/locale /openedx/locale
COPY --chown=app:app --from=python /opt/pyenv /opt/pyenv
COPY --chown=app:app --from=python-requirements /openedx/venv /openedx/venv
COPY --chown=app:app --from=python-requirements /openedx/requirements /openedx/requirements
COPY --chown=app:app --from=nodejs-requirements /openedx/nodeenv /openedx/nodeenv
COPY --chown=app:app --from=nodejs-requirements /openedx/edx-platform/node_modules /openedx/node_modules
RUN mv /openedx/node_modules/.bin /openedx/node_modules/bin

# Enable venv & nodeenv
ENV PATH /openedx/venv/bin:/openedx/node_modules/bin:/openedx/nodeenv/bin:${PATH}
ENV VIRTUAL_ENV /openedx/venv/
WORKDIR /openedx/edx-platform

# We install edx-platform here because it creates an egg-info folder in the current
# repo. We need both the source code and the virtualenv to run this command.
# TODO: Is it worth fixing up setup.py so that we can just run `pip install .` ?
RUN pip install -e .

# Copy scripts and put them on the path.
COPY --chown=app:app ./bin /openedx/bin
RUN chmod a+x /openedx/bin/*
ENV PATH /openedx/bin:${PATH}

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

# Compile i18n strings: in some cases, js locales are not properly compiled out of the box
# and we need to do a pass ourselves. Also, we need to compile the djangojs.js files for
# the downloaded locales.
RUN ./manage.py lms --settings=tutor.i18n compilejsi18n
RUN ./manage.py cms --settings=tutor.i18n compilejsi18n

{{ patch("openedx-dockerfile-pre-assets") }}

# Collect production assets. By default, only assets from the default theme
# will be processed. This makes the docker image lighter and faster to build.
# Only the custom themes added to /openedx/themes will be compiled.
# Here, we don't run "paver update_assets" which is slow, compiles all themes
# and requires a complex settings file. Instead, we decompose the commands
# and run each one individually to collect the production static assets to
# /openedx/staticfiles.
ENV NO_PYTHON_UNINSTALL 1
ENV NO_PREREQ_INSTALL 1

# TODO: This is necessary for _compile_sass currently but should be removed
RUN ln -s /openedx/node_modules
RUN cd node_modules && ln -s bin .bin

# We need to rely on a separate openedx-assets command to accelerate asset processing.
# For instance, we don't want to run all steps of asset collection every time the theme
# is modified.
# TODO: Can we remove the pavelib dependency?
RUN openedx-assets xmodule \
   && openedx-assets npm \
   && openedx-assets webpack --env=prod \
   && openedx-assets common
COPY --chown=app:app ./themes/ /openedx/themes/
RUN openedx-assets themes \
    && openedx-assets collect --settings=tutor.assets \
    # De-duplicate static assets with symlinks
    && rdfind -makesymlinks true -followsymlinks true /openedx/staticfiles/

# Create a data directory, which might be used (or not)
RUN mkdir /openedx/data

# service variant is "lms" or "cms"
ENV SERVICE_VARIANT lms
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.production

{{ patch("openedx-dockerfile") }}

EXPOSE 8000

#############################################################################
###### Intermediate image with dev/test dependencies

FROM production as development

# Install useful system requirements (as root)
USER root
RUN apt update && \
    apt install -y \
	  dnsutils \
	  iputils-ping \
	  telnet \
	  vim \
	  && \
    rm -rf /var/lib/apt/lists/*
USER app

# Add ipdb as default PYTHONBREAKPOINT
RUN pip install ipdb==0.13.4 ipython==7.27.0
ENV PYTHONBREAKPOINT=ipdb.set_trace

# Override any edx-platform files, as supplied by build context.
# Primarily, this allows Tutor to override /openedx/edx-platform/requirements
# when edx-platform is mounted in order to force a requirements re-install
# and static asset re-compilation below.
COPY ./dev/edx-platform-overrides /openedx/edx-platform

# Install dev requirements
RUN pip install -r requirements/edx/development.txt
RUN npm install --dev
RUN pip install -r requirements/edx/mounted.txt

# Recompile static assets: in development mode all static assets are stored in edx-platform,
# and the location of these files is stored in webpack-stats.json. If we don't recompile
# static assets, then production assets will be served instead.
RUN rm -r /openedx/staticfiles && \
    mkdir /openedx/staticfiles && \
    openedx-assets webpack --env=dev

{{ patch("openedx-dev-dockerfile-post-python-requirements") }}

# Default django settings
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.development

COPY ./dev/mounted-requirements.txt /openedx/mounted-requirements.txt
CMD ./manage.py $SERVICE_VARIANT runserver 0.0.0.0:8000

#############################################################################
###### Final image with production cmd
FROM production as final

# Run server
CMD uwsgi \
    --static-map /static=/openedx/staticfiles/ \
    --static-map /media=/openedx/media/ \
    --http 0.0.0.0:8000 \
    --thunder-lock \
    --single-interpreter \
    --enable-threads \
    --processes=${UWSGI_WORKERS:-2} \
    --buffer-size=8192 \
    --wsgi-file $SERVICE_VARIANT/wsgi.py

{{ patch("openedx-dockerfile-final") }}

