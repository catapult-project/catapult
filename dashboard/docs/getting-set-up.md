# Getting started with the Performance Dashboard

## Prerequisites

Running the tests, running the local server and
deploying all depends on having the [the App Engine
SDK](https://cloud.google.com/appengine/downloads).

After downloading and unpacking, you should add the path to the SDK to
both `PATH` and `PYTHONPATH`.

## Running the tests

To run the Python unit tests, use `bin/run_py_tests`. To run the front-end
component tests, use `bin/run_dev_server_tests`.

## Running a local instance

Run `bin/dev_server`; this sets up a temporary directory, adds links to
required libraries, and calls `dev_appserver.py` on that directory.  By
default, this starts a server on [localhost:8080](http://localhost:8080/).

To load sample graph or alert data from production, navigate to
[/load\_from\_prod](http://localhost:8080/load_from_prod).

## Deploying to production

To deploy, you can run `bin/deploy`, which prepares the
code to be deployed and runs `appcfg.py`. Note that this
doesn't set the new version as the default version; to do
this, you can use the versions page on the [Google Developers
Console](https://console.developers.google.com/) if you have edit or
owner permissions for the App Engine project; otherwise if you want to
request to set a new default version for chromeperf.appspot.com you can
contact chrome-perf-dashboard-team@google.com.

After deploying, there is a checklist to verify that no major functionality
has regressed: [deploy checklist](/dashboard/docs/deploy-checklist.md).

WARNING: Some changes to production may not be easily reversible; for
example `appcfg.py ... vacuum_indexes` will remove datastore indexes that
are not in your local index.yaml file, which may take more than 24 hours,
and will disable any queries that depend on those indexes.

## Where to find documentation

- [App Engine](https://developers.google.com/appengine/docs/python/)
- [Polymer](http://www.polymer-project.org/) (web component framework)
- [Flot](http://flotcharts.org/) (JS chart plotting library)
- [App engine stubs](https://developers.google.com/appengine/docs/python/tools/localunittesting)
- [Python mock](http://www.voidspace.org.uk/python/mock/)
