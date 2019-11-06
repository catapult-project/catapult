# Sheriff Config Service

This service is responsible for:

-   Validating a sheriff configuration.
-   Keeping a copy of the configuration(s) handy in Datastore/Memcache.
-   Providing a list of subscriptions which match for a given test identifier.

We've isolated this code into its own service, to allow us to test and validate
in isolation from the rest of the dashboard to let us determine a small scope.

## Testing

We recommend using Docker to build an isolated environment for testing the
sheriff-config service in isolation. Follow [steps](/tests/README.md) in tests/
to run the integration test for the sheriff-config service. The associated
`Dockerfile` and `docker-compose.yml` in tests/ contains the steps required to
develop an isolated version of the service, which can be tested locally.

To run the unit tests, we'll need the same requirements as the dashboard
installed and available in the environment.

NOTE: Because the dashboard still has parts of the code dependent on the
`python27` runtime, we cannot fully recommend using `virtualenv` for
building/testing the application.

Install the dependencies described in `requirements.txt`:

```
pip install --user --upgrade -r requirements.txt
```

You can either run the tests directly:

```
python -m unittest discover -p '*_test.py'
```

or through the dashboard test runner:

```
../../bin/run_py_tests
```

## Deployment

We'll use the `sheriff-config.yaml` file in this directory along with the
`requirements.txt` file for deployment.

```
gcloud app deploy sheriff-config.yaml
```
