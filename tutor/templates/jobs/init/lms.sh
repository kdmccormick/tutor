# When a local copy of edx-platform is bind-mounted, its
# egg-info directory may be missing or out of date. (The
# egg-info contains compiled Python entrypoint metadata, which
# is used by XBlock, Django App Plugins, and console scripts.)
# So, we regenerate egg-info by pip-installing this directory.
ENTRY_POINTS_INFO=Open_edX.egg-info/entry_points.txt
if [ ! -f "$ENTRY_POINTS_INFO" ] || [ "$ENTRY_POINTS_INFO" -ot setup.py ]; then
  pip install -e .
fi
dockerize -wait tcp://{{ MYSQL_HOST }}:{{ MYSQL_PORT }} -timeout 20s

# Wait for MongoDB.
{%- if MONGODB_HOST.startswith("mongodb+srv://") %}
echo "MongoDB is using SRV records, so we cannot wait for it to be ready"
{%- else %}
dockerize -wait tcp://{{ MONGODB_HOST }}:{{ MONGODB_PORT }} -timeout 20s
{%- endif %}

echo "Loading settings $DJANGO_SETTINGS_MODULE"

# Run migrations.
./manage.py lms migrate

# Create oauth2 apps for CMS SSO
# https://github.com/openedx/edx-platform/blob/master/docs/guides/studio_oauth.rst
./manage.py lms manage_user cms cms@openedx --unusable-password
./manage.py lms create_dot_application \
  --grant-type authorization-code \
  --redirect-uris "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ CMS_HOST }}/complete/edx-oauth2/" \
  --client-id {{ CMS_OAUTH2_KEY_SSO }} \
  --client-secret {{ CMS_OAUTH2_SECRET }} \
  --scopes user_id \
  --skip-authorization \
  --update cms-sso cms
./manage.py lms create_dot_application \
  --grant-type authorization-code \
  --redirect-uris "http://{{ CMS_HOST }}:8001/complete/edx-oauth2/" \
  --client-id {{ CMS_OAUTH2_KEY_SSO_DEV }} \
  --client-secret {{ CMS_OAUTH2_SECRET }} \
  --scopes user_id \
  --skip-authorization \
  --update cms-sso-dev cms


# Fix incorrect uploaded file path
if [ -d /openedx/data/uploads/ ]; then
  if [ -n "$(ls -A /openedx/data/uploads/)" ]; then
    echo "Migrating LMS uploaded files to shared directory"
    mv /openedx/data/uploads/* /openedx/media/
    rm -rf /openedx/data/uploads/
  fi
fi

# Create waffle switches to enable some features, if they have not been explicitly defined before
# Completion tracking: add green ticks to every completed unit
(./manage.py lms waffle_switch --list | grep completion.enable_completion_tracking) || ./manage.py lms waffle_switch --create completion.enable_completion_tracking on
