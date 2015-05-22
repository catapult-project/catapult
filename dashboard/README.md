# Dashboard

This is a App Engine web app for displaying performance test results.

Currently, the code is still being migrated from its original location;
the Python unit tests should run and the deployment script should work,
but the version of the dashboard currently here is incomplete.

See [online documentation](
http://www.chromium.org/developers/speed-infra/performance-dashboard).

## Directory structure

 * `static`: JavaScript and tests, CSS and images.
 * `templates`: HTML templates for each page.
 * `elements`: Polymer custom element definitions and tests.

## Prerequisites

Running the tests, running the local server and deploying all depends
on [the App Engine SDK](https://cloud.google.com/appengine/downloads).
After downloading and unpacking, you should add the path to the SDK
to both `PATH` and `PYTHONPATH`.

## Running the tests

To run all of the unit tests, you can run `./run_tests.py`. You can
also pass the import path to the test module to run a particular test,
for example `./run_tests.py dashboard.utils_test`.

## To run locally

To run a local App Engine server, you can run `dev\_appserver.py .`.
This requires installing the App Engine SDK. See [dev\_appserver](
https://cloud.google.com/appengine/docs/python/tools/devserver)
documentation.

## Deploying to production

To deploy, you can run `./deploy.sh`, which prepares the code to be
deployed and runs `appcfg.py`. This requires having the App Engine SDK
directory in your `PATH`.

This doesn't set the app as the default version, however. To do this,
you can use the versions page on the
[Google Developers Console](https://console.developers.google.com/),
or you can run `appcfg.py --application=<appid> --version=<version>

Other changes to production can be executed by running appcfg.py directly.
See [appcfg](
https://cloud.google.com/appengine/docs/python/tools/uploadinganapp)
documentation.

WARNING: Some changes to production may not be easily reversible; for example
`appcfg.py ... vacuum\_indexes` will remove datastore indexes that are
not in your local index.yaml file, which may take more than 24 hours,
and will disable any queries that depend on those indexes.
