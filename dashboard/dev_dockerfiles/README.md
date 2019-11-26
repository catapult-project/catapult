# Dashboard Dockerfile

This is an attempt to make the testing and deploying process for dashboard
more consistent and running everything in docker.

## One-time Set Up

### Install Docker and `docker-compose`.

This process requires that you have Docker installed locally.  Googlers, see
go/install-docker.

E.g. `sudo apt install docker-ce docker-compose`.

### Authenicate to gcloud

```
cd dev_dockerfiles
docker-compose run auth
```

## Process

### 1. Make Clean & Make

NOTE: The make process doesn't run automatically because you may run `make`
locally to test changes. If you run `make` locally, you need to manually run
`docker-compose run make` to get a consistent enviroment before testing.

```
cd dev_dockerfiles
docker-compose run make
```

### 2. Run Python Unit Tests

```
docker-compose run python-unittest
```

### 3. Deploy Dashboard

```
docker-compose run deploy
```
