Contributing
============

1.  **Please sign one of the contributor license agreements below.**
1.  Fork the repo, develop and test your code changes, add docs.
1.  Make sure that your commit messages clearly describe the changes.
1.  Send a pull request.

Here are some guidelines for hacking on `oauth2client`.

Using a Development Checkout
----------------------------

You’ll have to create a development environment to hack on
`oauth2client`, using a Git checkout:

-   While logged into your GitHub account, navigate to the `oauth2client`
    [repo][1] on GitHub.
-   Fork and clone the `oauth2client` repository to your GitHub account
    by clicking the "Fork" button.
-   Clone your fork of `oauth2client` from your GitHub account to your
    local computer, substituting your account username and specifying
    the destination as `hack-on-oauth2client`. For example:

    ```bash
    $ cd ${HOME}
    $ git clone git@github.com:USERNAME/oauth2client.git hack-on-oauth2client
    $ cd hack-on-oauth2client
    $ # Configure remotes such that you can pull changes from the oauth2client
    $ # repository into your local repository.
    $ git remote add upstream https://github.com:google/oauth2client
    $ # fetch and merge changes from upstream into master
    $ git fetch upstream
    $ git merge upstream/master
    ```

Now your local repo is set up such that you will push changes to your
GitHub repo, from which you can submit a pull request.

-   Create a virtualenv in which to install `oauth2client`:

    ```bash
    $ cd ~/hack-on-oauth2client
    $ virtualenv -ppython2.7 env
    ```

    Note that very old versions of virtualenv (virtualenv versions
    below, say, 1.10 or thereabouts) require you to pass a
    `--no-site-packages` flag to get a completely isolated environment.

    You can choose which Python version you want to use by passing a
    `-p` flag to `virtualenv`. For example, `virtualenv -ppython2.7`
    chooses the Python 2.7 interpreter to be installed.

    From here on in within these instructions, the
    `~/hack-on-oauth2client/env` virtual environment you created above will be
    referred to as `$VENV`. To use the instructions in the steps that
    follow literally, use the `export VENV=~/hack-on-oauth2client/env`
    command.

-   Install `oauth2client` from the checkout into the virtualenv using
    `setup.py develop`. Running `setup.py develop` **must** be done while
    the current working directory is the `oauth2client` checkout
    directory:

    ```bash
    $ cd ~/hack-on-oauth2client
    $ $VENV/bin/python setup.py develop
    ```

Running Tests
--------------

-   To run all tests for `oauth2client` on a single Python version, run
    `nosetests` from your development virtualenv (See
    **Using a Development Checkout** above).

-   To run the full set of `oauth2client` tests on all platforms, install
    [`tox`][2] into a system Python.  The `tox` console script will be
    installed into the scripts location for that Python.  While in the
    `oauth2client` checkout root directory (it contains `tox.ini`),
    invoke the `tox` console script.  This will read the `tox.ini` file and
    execute the tests on multiple Python versions and platforms; while it runs,
    it creates a virtualenv for each version/platform combination.  For
    example:

    ```bash
    $ sudo pip install tox
    $ cd ~/hack-on-oauth2client
    $ tox
    ```

Running System Tests
--------------------

-   To run system tests you can execute:

    ```bash
    $ tox -e system-tests
    $ tox -e system-tests3
    ```

    This alone will not run the tests. You'll need to change some local
    auth settings and download some service account configuration files
    from your project to run all the tests.

-   System tests will be run against an actual project and so you'll need to
    provide some environment variables to facilitate this.

    -   `OAUTH2CLIENT_TEST_JSON_KEY_PATH`: The path to a service account JSON
        key file; see `tests/data/gcloud/application_default_credentials.json`
        as an example. Such a file can be downloaded directly from the
        developer's console by clicking "Generate new JSON key". See private
        key [docs][3] for more details.
    -   `OAUTH2CLIENT_TEST_P12_KEY_PATH`: The path to a service account
        P12/PKCS12 key file. You can download this in the same way as a JSON
        key, just select "P12 Key" as your "Key type" when downloading.
    -   `OAUTH2CLIENT_TEST_P12_KEY_EMAIL`: The service account email
        corresponding to the P12/PKCS12 key file.
    -   `OAUTH2CLIENT_TEST_USER_KEY_PATH`: The path to a JSON key file for a
        user. If this is not set, the file created by running
        `gcloud auth login` will be used. See
        `tests/data/gcloud/application_default_credentials_authorized_user.json`
        for an example.
    -   `OAUTH2CLIENT_TEST_USER_KEY_EMAIL`: The user account email
        corresponding to the user JSON key file.

-   Examples of these can be found in `scripts/local_test_setup.sample`. We
    recommend copying this to `scripts/local_test_setup`, editing the values
    and sourcing them into your environment:

    ```bash
    $ source scripts/local_test_setup
    ```

Contributor License Agreements
------------------------------

Before we can accept your pull requests you'll need to sign a Contributor
License Agreement (CLA):

-   **If you are an individual writing original source code** and **you own
    the intellectual property**, then you'll need to sign an
    [individual CLA][4].
-   **If you work for a company that wants to allow you to contribute your
    work**, then you'll need to sign a [corporate CLA][5].

You can sign these electronically (just scroll to the bottom). After that,
we'll be able to accept your pull requests.

[1]: https://github.com/google/oauth2client
[2]: https://tox.readthedocs.org/en/latest/
[3]: https://cloud.google.com/storage/docs/authentication#generating-a-private-key
[4]: https://developers.google.com/open-source/cla/individual
[5]: https://developers.google.com/open-source/cla/corporate
