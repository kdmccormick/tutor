# The initialization job contains various re-install operations needed to be done
# on mounted directories (edx-platform, /mnt/*xblock, /mnt/<edx-ora, search, enterprise>)

echo "Performing additional setup for bind-mounted directories."
set -x # Echo out executed lines

cd /openedx/edx-platform || exit 1

# Whenever edx-platform or installable packages (e.g., xblocks) are mounted,
# during the image build, they are copied over to container and installed. This
# results in egg_info generation for the mounted directories. However, the
# egg_info is not carried over to host. When the containers are launched, the
# host directories without egg_info are mounted on runtime and disappear from
# pip list. To fix this, we `pip install` edx-platform (".") and every mounted
# package ("./mnt/*") again, re-generating the egg-infos.
for mounted_dir in . /mnt/*; do
    if [ -f $mounted_dir/setup.py ] && ! ls $mounted_dir/*.egg-info >/dev/null 2>&1 ; then
        echo "Unable to locate egg-info in $mounted_dir -- generating now."
        pip install -e $mounted_dir
    fi
done

# The same problem exists for edx-platform's compiled frontend assets, but recompiling
# them is very slow. So, instead of re-compiling, we create symlinks to an alternate
# directory in which we expect them to have been cached (/openedx/assets).
ln-assets /openedx/assets /openedx/edx-platform

set -x
echo "Done setting up bind-mounted directories."
