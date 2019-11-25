# Dashboard Dockerfile

This is an attempt to make the testing and deploying process for dashboard
more consistent and running everything in docker.

NOTE: The make process doesn't run automaticly because you may run `make`
locally to test change. If you run `make` locally, you need to manually run
`docker-compose run make` to get a consistent enviroment before testing.

## Make Clean & Make

```
docker-compose run make
```

## Run Python Unit Tests

```
docker-compose run python-unittest
```

## Deply Dashboard

```
docker-compose run deploy
```

...and if not authenticated

```
docker-compose run auth
```