# Dashboard Dockerfile

This is an attempt to make the testing and deploying process for dashboard
more consistent and running everything in docker.

## One-time Set Up

### Install Docker and `docker-compose`.

This process requires that you have Docker installed locally. Googlers, see
go/install-docker.

E.g. `sudo apt install docker-ce docker-compose`.

### Authenicate to gcloud

```
cd dev_dockerfiles
docker-compose run auth
```

## Usage

### Run Python Unit Tests

```
docker-compose run python-unittest
```

### Deploy Dashboard

```
docker-compose run deploy-dashboard
```

### Deploy Pinpoint

```
docker-compose run deploy-pinpoint
```