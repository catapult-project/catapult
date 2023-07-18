# update-traffic

This tool automates some of the weekly deployment steps for chromeperf appengine services.

It checks the list of available GAE service versions to find two specific version IDs: the newest version, and the version that currently has a 1.0 allocation of traffic.  If the two version IDs are not the same, it will attempt to update the appropriate .yaml configuration file in your local checkout such that the latest version ID is the one with a 1.0 share of the service's traffic allocation.

# Usage

Since this hasn't been evaluated very heavily, we don't have a deployed binary package for it yet.
However you should be able to build and run it using the `go` command like so:

```
go run update-traffic.go [options]
```

The intended use case is for updating the traffic allocation entries in various per-service yaml files.  Typically you will want to make a separate CL for each of these updates, and run `update-traffic` once per CL to generate the changed lines.

If you give it a `-checkout-base` flag, it will edit files in your checkout.  If you do not specify this flag, the command will print a summary of the service/version/traffic allocation updates it would have made.

# Example
Suppose you are doing a weekly deployment, which requires a separate CL for each service traffic allocation update.

You could do the following once for each service (substitute `api`, `default`, `pinpoint`, etc for `perf-issue-service` below). From this directory (which should be something like `catapult/dashboard/go/src/update-traffic` in your checkout):
```
git checkout -b update-perf-issue-service
go run update-traffic.go -checkout-base ../../../.. -service-id perf-issue-service
git commit -am 'update yaml'
git cl upload
```

Then submit each CL for review in gerrit as described by go/berf-rotation-playbook in the Deployment section.

