# The initialization job contains various re-install and asset-symlinking
# operations needed to be done on mounted directories (edx-platform,
# /mnt/*xblock, /mnt/<edx-ora, search, enterprise>)

echo "Performing additional setup for bind-mounted directories."
set -x # Echo out executed lines

cd /openedx/edx-platform || exit 1  # Fail early if edx-platform is missing

pip-install-mounted

ln-assets /openedx/assets /openedx/edx-platform

set +x
echo "Done setting up bind-mounted directories."
