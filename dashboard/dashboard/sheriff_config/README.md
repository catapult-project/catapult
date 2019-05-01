# Sheriff Config Service

This service is responsible for:

-   Validating a sheriff configuration.
-   Keeping a copy of the configuration(s) handy in Datastore/Memcache.
-   Providing a list of subscriptions which match for a given test identifier.

We've isolated this code into its own service, to allow us to test and validate
in isolation from the rest of the dashboard to let us determine a small scope.

## Testing

TODO(dberris): Write up how we're testing this service in isolation.

We recommend using `virtualenv` to scope all the dependencies into a logically
isolated environment. We'll use the following for testing:

```
virtualenv --python python3 $HOME/sheriff-config-env
source $HOME/sheriff-config-env/bin/activate
pip install -r requirements.txt
```

We'll use `make` to perform all required code generation (mostly for protocol
buffers).

```
make
```

## Deployment

We'll use the `sheriff-config.yaml` file in this directory along with the
`requirements.txt` file for deployment.

```
gcloud app deploy sheriff-config.yaml
```
