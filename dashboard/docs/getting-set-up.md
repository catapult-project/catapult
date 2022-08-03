# Getting started with the Performance Dashboard

## Prerequisites

1. Make sure you have Python 2.7.x installed. Python 3.x is not supported.
2. [Download the Google Cloud SDK.](https://cloud.google.com/sdk/downloads)
3. Update the Cloud SDK and set the default project to your project ID by
   invoking the following commands:
   ```
   gcloud components update
   gcloud components install app-engine-python
   gcloud config set project [PROJECT-ID]
   ```
   Replace `[PROJECT-ID]` with your project ID. For chromeperf.appspot.com,
   it's `chromeperf`.
4. Make sure that gcloud is in your PATH.
5. Make sure that you have installed
[protoc](https://github.com/protocolbuffers/protobuf).

## Running the tests

To run the Python unit tests, use `bin/run_py_tests`. To run the front-end
component tests, use `bin/run_dev_server_tests`.

## Running a local instance

Running a local instance (i.e., a dev server) of the Performance Dashboard is
only supported on Linux. First, you need to do the following one-time setups:

- Make sure you have depot\_tools installed and in your PATH.
- Run the following commands:
```
sudo apt install nodejs
GAE_SDK_PATH=~/gae_sdk
echo infra/gae_sdk/python/all latest | cipd ensure -root $GAE_SDK_PATH -ensure-file -
export PYTHONPATH=$GAE_SDK_PATH
export PATH=$PATH:$GAE_SDK_PATH
```

You may want to preserve the changes of `PYTHONPATH` and `PATH` to your shell
environment settings, otherwise you will need to reapply the changes each time.

After the setups, run `vpython bin/dev_server`;
this sets up a temporary directory, adds links to
required libraries, and calls `dev_appserver.py` on that directory.  By
default, this starts a server on [localhost:8080](http://localhost:8080/).

To load sample graph or alert data from production, navigate to
[/load\_from\_prod](http://localhost:8080/load_from_prod).

## Deploying to production

See [Docker deploy](/dashboard/dev_dockerfiles/README.md).

## Where to find documentation

- [App Engine](https://developers.google.com/appengine/docs/python/)
- [Polymer](http://www.polymer-project.org/) (web component framework)
- [Flot](http://flotcharts.org/) (JS chart plotting library)
- [App engine stubs](https://developers.google.com/appengine/docs/python/tools/localunittesting)
- [Python mock](http://www.voidspace.org.uk/python/mock/)
