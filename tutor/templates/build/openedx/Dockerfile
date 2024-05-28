# syntax=docker/dockerfile:1

FROM docker.io/ubuntu:20.04 as minimal
LABEL maintainer="Overhang.io <contact@overhang.io>"
ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install \
        build-essential \
        curl \
        git \
        language-pack-en \
        --yes
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

FROM minimal as git-clone-edx-platform
ARG EDX_PLATFORM_REPOSITORY={{ EDX_PLATFORM_REPOSITORY }}
ARG EDX_PLATFORM_VERSION={{ EDX_PLATFORM_VERSION }}
RUN mkdir -p /openedx/edx-platform && \
    git clone $EDX_PLATFORM_REPOSITORY --branch $EDX_PLATFORM_VERSION --depth 1 /openedx/edx-platform
WORKDIR /openedx/edx-platform
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

FROM scratch as edx-platform
COPY --from=git-clone-edx-platform /openedx/edx-platform /

{% for name in iter_mounted_directories(MOUNTS, "openedx") %}
FROM scratch as mnt-{{ name }}
{% endfor %}

FROM minimal as pyenv
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install \
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
		--yes
RUN git clone https://github.com/pyenv/pyenv $PYENV_ROOT --branch v2.3.36 --depth 1
RUN $PYENV_ROOT/bin/pyenv install $PYTHON_VERSION
RUN $PYENV_ROOT/versions/$PYTHON_VERSION/bin/python -m venv /openedx/venv
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        setuptools==69.1.1 \
		pip==24.0 \
		wheel==0.43.0

FROM pyenv as nodeenv
WORKDIR /openedx/edx-platform
COPY --from=edx-platform /requirements/edx/assets.txt requirements/edx/assets.txt
RUN pip install -r requirements/edx/assets.txt
ENV PATH /openedx/nodeenv/bin:/openedx/venv/bin:${PATH}
RUN nodeenv /openedx/nodeenv --node=18.20.1 --prebuilt
ARG NPM_REGISTRY={{ NPM_REGISTRY }}
COPY --from=edx-platform /package.json package.json
COPY --from=edx-platform /package-lock.json package-lock.json
COPY --from=edx-platform /scripts/copy-node-modules.sh scripts/copy-node-modules.sh
RUN --mount=type=cache,target=/root/.npm,sharing=shared \
    npm clean-install --no-audit --registry=$NPM_REGISTRY

FROM nodeenv as js-src
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
COPY --link --from=nodeenv /openedx/edx-platform/common/static/common/js/vendor common/static/common/js/vendor
COPY --link --from=nodeenv /openedx/edx-platform/common/static/common/css/vendor common/static/common/css/vendor

FROM js-src as js-prod
RUN npm run webpack

FROM js-src as js-dev
RUN npm run webpack-dev

FROM nodeenv as sass
COPY --link --from=edx-platform /scripts/compile_sass.py scripts/compile_sass.py
COPY --link --from=edx-platform /common/static common/static
COPY --link --from=edx-platform /lms/static/sass lms/static/sass
COPY --link --from=edx-platform /lms/static/sass/partials lms/static/sass/partials
COPY --link --from=edx-platform /lms/static/certificates/sass lms/static/certificates/sass
COPY --link --from=edx-platform /cms/static/sass cms/static/sass
COPY --link --from=edx-platform /cms/static/sass/partials cms/static/sass/partials
COPY --link --from=edx-platform /xmodule/assets xmodule/assets
COPY --link --from=edx-platform /lms/static/css/vendor lms/static/css/vendor

FROM sass as css-prod
RUN npm run compile-sass -- --skip-themes
COPY --link ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default

FROM sass as css-dev
RUN npm run compile-sass -- --skip-themes --env=dev
COPY --link ./themes/ /openedx/themes/
RUN npm run compile-sass -- --skip-default --env=dev

FROM nodeenv as fullenv
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update  && \
    apt install \
        libgeos-dev \
        libmysqlclient-dev \
        libxmlsec1-dev \
        software-properties-common \
		--yes
COPY --link --from=edx-platform /requirements/edx/base.txt /openedx/edx-platform/requirements/edx/base.txt
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        -r /openedx/edx-platform/requirements/edx/base.txt \
        django-redis==5.4.0 \
        uwsgi==2.0.24 \
        'openedx-scorm-xblock>=17.0.0,<18.0.0'
{{ patch("openedx-dockerfile-post-python-requirements") }}
{% for extra_requirements in OPENEDX_EXTRA_PIP_REQUIREMENTS %}
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install '{{ extra_requirements }}'
{% endfor %}
{% for name in iter_mounted_directories(MOUNTS, "openedx") %}
COPY --link --from=mnt-{{ name }} / /mnt/{{ name }}
RUN pip install -e "/mnt/{{ name }}"
{% endfor %}

FROM fullenv as fullenv-dev
COPY --link --from=edx-platform /requirements/edx/development.txt /openedx/edx-platform/requirements/edx/development.txt
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \
    pip install \
        -r /openedx/edx-platform/requirements/edx/development.txt \
        ipdb==0.13.13 \
        ipython==8.24.0

FROM minimal as app
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update  && \
    apt install \
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
        mysql-client \
        ntp \
        pkg-config \
        rdfind \
        --yes
ARG APP_USER_ID=1000
RUN if [ "$APP_USER_ID" = 0 ]; then echo "app user may not be root" && false; fi
RUN useradd --no-log-init --home-dir /openedx --create-home --shell /bin/bash --uid ${APP_USER_ID} app
USER ${APP_USER_ID}
COPY --link --from=docker.io/powerman/dockerize:0.19.0 /usr/local/bin/dockerize /usr/local/bin/dockerize
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv /opt/pyenv /opt/pyenv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv /openedx/nodeenv /openedx/nodeenv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv /openedx/venv /openedx/venv
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv /mnt /mnt
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=edx-platform / /openedx/edx-platform
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv \
    /openedx/edx-platform/node_modules \
    /openedx/edx-platform/node_modules
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv \
   /openedx/edx-platform/common/static/common/js/vendor \
   /openedx/edx-platform/common/static/common/js/vendor
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv \
    /openedx/edx-platform/common/static/common/css/vendor \
    /openedx/edx-platform/common/static/common/css/vendor
RUN mkdir -p /openedx/config /openedx/edx-platform/lms/envs/tutor /openedx/edx-platform/cms/envs/tutor
COPY --link revisions.yml /openedx/config/
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/lms/*.py /openedx/edx-platform/lms/envs/tutor/
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/cms/*.py /openedx/edx-platform/cms/envs/tutor/
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} ./bin /openedx/bin
RUN chmod a+x /openedx/bin/*
ENV PATH /openedx/bin:${PATH}
ENV SERVICE_VARIANT lms
ENV LMS_CFG /openedx/config/lms.env.yml
ENV CMS_CFG /openedx/config/cms.env.yml
ENV REVISION_CFG /openedx/config/revisions.yml
RUN mkdir /openedx/data
WORKDIR /openedx/edx-platform
RUN pip install -e .
{{ patch("openedx-dockerfile") }}
EXPOSE 8000

FROM app as locales
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

FROM app as production
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=locales \
	/openedx/edx-platform/conf/locale \
	/openedx/edx-platform/conf/locale
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=locales \
	/openedx/edx-platform/conf/plugins-locale \
	/openedx/edx-platform/conf/plugins-locale
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=js-prod \
	/openedx/staticfiles \
	/openedx/staticfiles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=js-prod \
	/openedx/edx-platform/common/static/bundles \
	common/static/bundles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-prod \
	/openedx/edx-platform/lms/static/css \
	lms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-prod \
	/openedx/edx-platform/lms/static/certificates/css \
	lms/static/certificates/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-prod \
	/openedx/edx-platform/cms/static/css \
	cms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-prod \
	/openedx/themes \
	/openedx/themes
RUN ./manage.py lms collectstatic --noinput --settings=tutor.assets
RUN ./manage.py cms collectstatic --noinput --settings=tutor.assets
RUN rdfind -makesymlinks true -followsymlinks true /openedx/staticfiles/
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} settings/uwsgi.ini .
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.production
ENV UWSGI_WORKERS=2
CMD uwsgi uwsgi.ini
{{ patch("openedx-dockerfile-final") }}

FROM app as development
USER root
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && \
    apt install \
        dnsutils \
        iputils-ping \
        telnet \
        vim \
        --yes
USER app
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=fullenv-dev /openedx/venv /openedx/venv
RUN pip install -e .
{{ patch("openedx-dev-dockerfile-post-python-requirements") }}
ENV PYTHONBREAKPOINT=ipdb.set_trace
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=js-dev \
	/openedx/staticfiles/webpack-stats.json \
	/openedx/staticfiles/webpack-stats.json
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=js-dev \
	/openedx/staticfiles/studio/webpack-stats.json \
	/openedx/staticfiles/studio/webpack-stats.json
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=js-dev \
	/openedx/edx-platform/common/static/bundles \
	common/static/bundles
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-dev \
	/openedx/edx-platform/lms/static/css \
	lms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-dev \
	/openedx/edx-platform/lms/static/certificates/css \
	lms/static/certificates/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-dev \
	/openedx/edx-platform/cms/static/css \
	cms/static/css
COPY --link --chown=${APP_USER_ID}:${APP_USER_ID} --from=css-dev \
	/openedx/themes \
	/openedx/themes
ENV DJANGO_SETTINGS_MODULE lms.envs.tutor.development
CMD ./manage.py $SERVICE_VARIANT runserver 0.0.0.0:8000
