.. _development:

Open edX development
====================

In addition to running Open edX in production, Tutor can be used for local development of Open edX. This means that it is possible to hack on Open edX without setting up a Virtual Machine. Essentially, this replaces the devstack provided by edX.


First-time setup
----------------

First, ensure you have already :ref:`installed Tutor <install>` (for development against the named releases of Open edX) or :ref:`Tutor Nightly <nightly>` (for development against Open edX's master branches).

Then, launch the developer platform setup process::

    tutor dev quickstart

This will perform several tasks for you. It will:

* stop any existing locally-running Tutor containers,

* disable HTTPS,

* set your ``LMS_HOST`` to `local.overhang.io <http://local.overhang.io>`_ (a convenience domain that simply `points at 127.0.0.1 <https://dnschecker.org/#A/local.overhang.io>`_),

* prompt for a platform details (with suitable defaults),

* build an ``openedx-dev`` image, which is based ``openedx`` production image but is `specialized for developer usage`_,

* start LMS, CMS, supporting services, and any plugged-in services,

* ensure databases are created and migrated, and

* run service initialization scripts, such as service user creation and Waffle configuration.

Once setup is complete, the platform will be running in the background:

* LMS will be accessible at `http://local.overhang.io:8000 <http://local.overhang.io:8000>`_.
* CMS will be accessible at `http://studio.local.overhang.io:8001 <http://studio.local.overhang.io:8001>`_.
* Plugged-in services should be accessible at their documented URLs.


Stopping the platform
---------------------

To bring down your platform's containers, simply run::

  tutor dev stop


Starting the platform back up
-----------------------------

Once you have used ``quickstart`` once, you can start the platform in the future with the lighter-weight ``start`` command, which brings up containers but does not perform any initialization tasks::

  tutor dev start     # Run platform in the same terminal ("attached")
  tutor dev start -d  # Or, run platform the in the background ("detached")

Nonetheless, ``quickstart`` is idempotent, so it is always safe to run it again in the future without risk to your data. In fact, you may find it useful to use this command as a one-stop-shop for pulling images, running migrations, initializing new plugins you have enabled, and/or executing any new initialization steps that may have been introduced since you set up Tutor::

  tutor dev quickstart --pullimages


Running arbitrary commands
--------------------------

To run any command inside one of the containers, run ``tutor dev run [OPTIONS] SERVICE [COMMAND] [ARGS]...``. For instance, to open a bash shell in the LMS or CMS containers::

    tutor dev run lms bash
    tutor dev run cms bash

To open a python shell in the LMS or CMS, run::

    tutor dev run lms ./manage.py lms shell
    tutor dev run cms ./manage.py cms shell

You can then import edx-platform and django modules and execute python code.

To collect assets, you can use the ``openedx-assets`` command that ships with Tutor::

    tutor dev run lms openedx-assets build --env=dev


.. _specialized for developer usage: 

Rebuilding the openedx-dev image
--------------------------------

The ``openedx-dev`` Docker image is based on the same ``openedx`` image used by ``tutor local ...`` to run LMS and CMS. However, it has a few differences to make it more convenient for developers:

- The user that runs inside the container has the same UID as the user on the host, to avoid permission problems inside mounted volumes (and in particular in the edx-platform repository).

- Additional Python and system requirements are installed for convenient debugging: `ipython <https://ipython.org/>`__, `ipdb <https://pypi.org/project/ipdb/>`__, vim, telnet.

- The edx-platform `development requirements <https://github.com/openedx/edx-platform/blob/open-release/nutmeg.master/requirements/edx/development.in>`__ are installed.


If you are using a custom ``openedx`` image, then you will need to rebuild ``openedx-dev`` every time you modify ``openedx``. To so, run::

    tutor dev dc build lms


.. _bind_mounts:

Sharing directories with containers
-----------------------------------

At some point while developing Open edX, you will need to run the platform with edited code/assets so that you can, for example, preview and debug your feature changes. One way to do this is to re-build container images with modified files. However, this takes too long when you are trying to quickly make incremental changes to the platform. It would be much easier if you could just run the platform, but with certain container directories replaced with modified ones from your host.

Fortunately, Docker supports this: it's called "bind-mounting", and Tutor makes it easy via the ``-m/--mount`` command option. 

.. _mount_option:

Introducing: the ``--mount`` option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``quickstart``, ``run``, ``init`` and ``start`` subcommands of ``tutor dev`` and ``tutor local`` support the ``-m/--mount`` option (see :option:`tutor dev start -m`) which can take two different forms.

Explicit form
^^^^^^^^^^^^^
::

    tutor dev start --mount=service1,service2:source/of/myfolder:/destination/for/myfolder

This means: *Start Open edX, with the the host directory* **source/of/myfolder** *bind-mounted to* **/destination/for/myfolder** *in the containers for* **service1** *and* **service2.**

.. note:: Relative, absolute, and tilde-prefixed (``~/...``) paths can all be used for the host directory. However, only full absolute paths can be used for the container directory.

Implicit form
^^^^^^^^^^^^^
::

    tutor dev start --mount=source/of/myfolder

This means: *Start Open edX, with the host directory* **source/of/myfolder** *automatically bind-mounted to sensible container directories based on the directory name* **myfolder**.

Now, if you ran this literal command, Tutor would tell you that it didn't know where to mount **myfolder**. As you will see below, though, there are several folders that Tutor *does* know how to automatically mount for you.

Example
^^^^^^^

Assuming your Open edX repositories are located within ``~/code``, to run a Django shell in the CMS container with your copy of edx-platform mounted, you could run either of these commands::

    # Implicit version
    tutor dev run -m ~/code/edx-platform cms ./manage.py cms shell

    # Explicit version
    tutor dev run \
        --mount=lms:~/code/edx-platform:/openedx/edx-platform
        cms ./manage.py cms shell

.. _edx_platform_dev_env:

Setting up a development environment for edx-platform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that you understand ``--mount``, we can tell Tutor to run a fork of edx-platform from your host. We will assume that your code is located on your host at ``~/code/edx-platform``, although this is not a requirement for development.

First of all, make sure that you are working off the latest release tag (unless you are running the Tutor :ref:`nightly <nightly>` branch). See the :ref:`fork edx-platform section <edx_platform_fork>` for more information.

Then, you should run the following commands::

    # Run bash in the lms container
    tutor dev run --mount=~/code/edx-platform lms bash

    # Run edx-platform's setup.py
    pip install -e .

    # Install nodejs packages into node_modules/
    npm install

    # Rebuild static assets
    openedx-assets build --env=dev

    # Exit the lms container
    exit

.. hint:: This can also be done in one single, long command: ``tutor dev run -m ~/code/edx-platform lms bash -c 'pip install -e . && npm i && openedx-assets build --env=dev'``

After running all these commands, your edx-platform repository will be ready for local development. To debug a local edx-platform repository, you can then add a `python breakpoint <https://docs.python.org/3/library/functions.html#breakpoint>`__ with ``breakpoint()`` anywhere in your code and run::

    tutor dev start --mount=~/edx-platform lms

The default debugger is ``ipdb.set_trace``. ``PYTHONBREAKPOINT`` can be modified by setting an environment variable in the Docker imamge.

If LMS isn't running, this will start it in your terminal. If an LMS container is already running background, this command will stop it, recreate it, and attach your terminal to it. Later, to detach your terminal without stopping the container, just hit ``Ctrl+z``. 

Every time you run ``tutor dev start``, your platform is updated to match the ``--mount`` options that were provided, if any. In other words, the latest invocation of ``start`` "wins" when determining what should be mounted. So, to re-start the platform *without* your fork edx-platform mounted, simply run::

    tutor dev start

and to re-start it again *with* your fork mounted, run::

    tutor dev start --mount=~/code/edx-platform


Mounting virtual environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your modifications *do not affect an application's Python requirements*, then mounting & preparing the application repository as described above will be enough for the purposes of previewing and debugging. That is because the Python virtual environment build into the container image will have all the correct packages installed.

On the other hand, if your modifications require that Python packages to be added, removed, upgraded, or downgraded, then you will also want to **mount a local Python virtual environment**.

First, copy an existing virtual environment from a service container whose requirements you're modifying (in our case, ``lms`` or ``cms``)::

    rm -rf ~/venv-openedx  # Delete this virtual environment if it already exists.
    tutor dev copyfrom lms /openedx/venv ~/venv-openedx

Then, install Python requirements, with your modified repository and new local virtual environment both mounted::

    tutor dev run --mount=~/code/edx-platform --mount=~/venv-openedx lms \
        pip install -r requirements/edx/development.txt

.. note:: If you further modify Python requirements in the future, run this command again.

Finally, you can (re-) start Open edX using your mounted code and virtual environment::

    tutor dev start --mount=~/code/edx-platform --mount=~/venv-openedx

.. note:: The packages in your local virtual environment will persist, even after containers are stopped.

That's it! By the way, did you notice that we're using the implicit form of ``--mount`` again here? The explicit form would have been much longer::

    tutor dev start \
        --mount=lms,lms-worker,lms-job,cms,cms-worker,cms-job:~/code/edx-platform:/openedx/edx-platform \
        --mount=lms,lms-worker,lms-job,cms,cms-worker,cms-job:~/venvs/venv-openedx:/openedx/venv

The shorter command works because Tutor will automatically mount folders named ``venv-openedx`` to all LMS and CMS containers at the right location, ``/openedx/venv``.

Mounting packages
~~~~~~~~~~~~~~~~~

A slightly more advanced use case is mounting modified versions of Python packages so that they can be installed into edx-platform, allowing you to preview the results of your package changes in the LMS and Studio. For example, imagine we have made changes to xblock-drag-and-drop-v2, and now we want to preview them in a running platform.

First, we would prepare a local virtual environment as described above. Then, we would mount our modified block and install it into our local virtual environment::

    tutor dev run \
        --mount=~/code/xblock-drag-and-drop-v2 \
        --mount=~/venv-openedx \
        lms pip install -e /openedx/packages/xblock-drag-and-drop-v2

Now, we can (re-)start Open edX::

    tutor dev start \
        --mount=~/code/xblock-drag-and-drop-v2 \
        --mount=~/code/edx-platform \
        --mount=~/venv-openedx

.. hint:: If no changes have been made to the edx-platform repository in this scenario, then ``--mount=~/code/edx-platform`` can be omitted from the command above.

Again, notice that we mounted xblock-drag-and-drop-v2 using the implicit form. Tutor automatically mounts to LMS and CMS containers any folder that:

* begins with "xblock-" or
* begins with "platform-plugin-."

For packages that don't follow these naming conventions, you will need to either rename the package's containing folder, or use the explicit form of ``--mount``. For example, to run LMS with a local fork of the edx-django-utils package, we would run::

    tutor dev run \
        --mount=lms,lms-worker,lms-job:~/code/edx-django-utls:/openedx/packages/edx-django-utils \
        --mount=~/venv-openedx \
        lms pip install -e /openedx/packages/edx-django-utils
    tutor dev start \
        --mount=lms,lms-worker,lms-job:~/code/edx-django-utls:/openedx/packages/edx-django-utils \
        --mount=~/code/edx-platform \
        --mount=~/venv-openedx

Setting up a development environment for other services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many plugins add extra services to Tutor. For example, the tutor-discovery plugin adds a "discovery" service. The strategies above can generally be modified to work with other Python services.

For example, to prepare and run the discovery service using a local fork of course-discovery and local virtual environment, you might enable tutor-discovery and then run::

    # Prepare local fork for development.
    # For exact preparation steps for any given plugin, consult the plugin's documentation.
    # In the case of discovery, we need to install nodejs requirements into node_modules/
    tutor dev run --mount=~/code/course-discovery discovery npm install

    # Prepare discovery virtual environment.
    rm -rf ~/venv-discovery
    tutor dev copyfrom discovery /openedx/venv ~/venv-discovery
    tutor dev run --mount=~/code/course-discovery --mount=~/venv-discovery discovery \
        pip install -r requirements/local.txt

    # (re-)start the platform, with discovery code and virtual environment mounted.
    tutor dev start --mount=~/code/course-discovery --mount=~/venv-discovery

Note that we were able to use the implicit version of ``-m/--mount``, since:

* The tutor-discovery plugin tells Tutor where any folder named ``course-discovery`` should be mounted. Most plugins that add services to Tutor provide this as a convenience.
* Tutor will mount any folder named ``venv-<SERVICE>`` to ``/openedx/venv`` for any containers of ``<SERVICE>``.

Implicit vs. explicit mounting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This table collects the various folder name patterns that work with the implicit form of ``-m/--mount``:

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Implicit Form
     - Equivalent Explicit Form
   * - ``-m edx-platform``
     - ``-m lms,lms-worker,lms-job,cms,cms-worker,cms-job:edx-platform:/openedx/edx-platform``
   * - ``-m venv-openedx``
     - ``-m lms,lms-worker,lms-job,cms,cms-worker,cms-job:venv-openedx:/openedx/venv``
   * - ``-m venv-SERVICE``
     - ``-m SERVICE,SERVICE-job:venv-SERVICE:/openedx/venv``
   * - ``-m xblock-XYZ``
     - ``-m lms,lms-worker,lms-job,cms,cms-worker,cms-job:xblock-XYZ:/openedx/packages/xblock-XYZ``
   * - ``-m platform-plugin-ABC``
     - ``-m lms,lms-worker,lms-job,cms,cms-worker,cms-job:platform-plugin-ABC:/openedx/packages/platform-plugin-ABC``


This table collects the various folder name patterns that work with the implicit form of ``-m/--mount``::

    +------------------------+------------------------------------------------------------------------------------------------------------+
    | Implicit Form          | Equivalent Explicit Form                                                                                   |
    +========================+============================================================================================================+
    | -m edx-platform        | -m lms,lms-worker,lms-job,cms,cms-worker,cms-job:edx-platform:/openedx/edx-platform                        |
    +------------------------+------------------------------------------------------------------------------------------------------------+
    | -m venv-openedx        | -m lms,lms-worker,lms-job,cms,cms-worker,cms-job:venv-openedx:/openedx/venv                                |
    +------------------------+------------------------------------------------------------------------------------------------------------+
    | -m venv-SERVICE        | -m SERVICE,SERVICE-job:venv-SERVICE:/openedx/venv                                                          |
    +------------------------+------------------------------------------------------------------------------------------------------------+
    | -m xblock-XYZ          | -m lms,lms-worker,lms-job,cms,cms-worker,cms-job:xblock-XYZ:/openedx/packages/xblock-XYZ                   |
    +------------------------+------------------------------------------------------------------------------------------------------------+
    | -m platform-plugin-ABC | -m lms,lms-worker,lms-job,cms,cms-worker,cms-job:platform-plugin-ABC:/openedx/packages/platform-plugin-ABC |
    +------------------------+------------------------------------------------------------------------------------------------------------+

Override docker-compose volumes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All the above strategies require that you explicitly pass the ``-m/--mount`` options to every ``run``, ``start`` or ``init`` command, which may be inconvenient. To address these issues, you can create a ``docker-compose.override.yml`` file that will specify custom volumes to be used with all ``dev`` commands::

    vim "$(tutor config printroot)/env/dev/docker-compose.override.yml"

You are then free to bind-mount any directory to any container. For instance, to mount your own edx-platform fork::

    version: "3.7"
    services:
      lms:
        volumes:
          - /path/to/edx-platform:/openedx/edx-platform
      cms:
        volumes:
          - /path/to/edx-platform:/openedx/edx-platform
      lms-worker:
        volumes:
          - /path/to/edx-platform:/openedx/edx-platform
      cms-worker:
        volumes:
          - /path/to/edx-platform:/openedx/edx-platform

This override file will be loaded when running any ``tutor dev ..`` command. The edx-platform repo mounted at the specified path will be automatically mounted inside all LMS and CMS containers. With this file, you should no longer specify the ``-m/--mount`` option from the command line.

.. note::
    The ``tutor local`` commands load the ``docker-compose.override.yml`` file from the ``$(tutor config printroot)/env/local/docker-compose.override.yml`` directory. One-time jobs from initialisation commands load the ``local/docker-compose.jobs.override.yml`` and ``dev/docker-compose.jobs.override.yml``.

Common tasks
------------

XBlock and edx-platform plugin development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TODO: Delete in favor of "Mounting packages"?

In some cases, you will have to develop features for packages that are pip-installed next to the edx-platform. This is quite easy with Tutor. Just add your packages to the ``$(tutor config printroot)/env/build/openedx/requirements/private.txt`` file. To avoid re-building the openedx Docker image at every change, you should add your package in editable mode. For instance::

    echo "-e ./mypackage" >> "$(tutor config printroot)/env/build/openedx/requirements/private.txt"

The ``requirements`` folder should have the following content::

    env/build/openedx/requirements/
        private.txt
        mypackage/
            setup.py
            ...

You will have to re-build the openedx Docker image once::

    tutor images build openedx

You should then run the development server as usual, with ``start``. Every change made to the ``mypackage`` folder will be picked up and the development server will be automatically reloaded.

Running edx-platform unit tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It's possible to run the full set of unit tests that ship with `edx-platform <https://github.com/openedx/edx-platform/>`__. To do so, run a shell in the LMS development container::

    tutor dev run lms bash

Then, run unit tests with ``pytest`` commands::

    # Run tests on common apps
    unset DJANGO_SETTINGS_MODULE
    unset SERVICE_VARIANT
    export EDXAPP_TEST_MONGO_HOST=mongodb
    pytest common
    pytest openedx

    # Run tests on LMS
    export DJANGO_SETTINGS_MODULE=lms.envs.tutor.test
    pytest lms

    # Run tests on CMS
    export DJANGO_SETTINGS_MODULE=cms.envs.tutor.test
    pytest cms

.. note::
    Getting all edx-platform unit tests to pass on Tutor is currently a work-in-progress. Some unit tests are still failing. If you manage to fix some of these, please report your findings in the `Open edX forum <https://discuss.openedx.org/tag/tutor>`__.
