# Cloud Functions

This directory hosts the source code for production Cloud Functions in the chromeperf project.

# How To Deploy Functions
To manually deploy all functions in this library, call:

```
gcloud builds submit --region=us-central1 --config cloudbuild.yaml .
```

This will execute cloudbuild.yaml and will deploy all functions in parallel.

# How To Test Locally

Prerequisites for this method:

- Install `functions-framework`: https://cloud.google.com/functions/docs/running/function-frameworks
  - This method is not intended to play nicely with vpython or venv or other python dependency resolution hacks.  It just uses pip. So if you
  can't use pip for whatever reason then this README cannot help you.
  - you may need to install `pip` first (e.g. on a cloudtop where it may not be there already)
  - you may need to run the `pip install` command with `--break-system-packages` to get around an error message
  - e.g. `pip install -r requirements.txt --break-system-packages` from this directory
- `curl`: should be installed already on most workstation environments
- `gcloud`: should also be installed before proceeding
- run `gcloud auth application-default login` (once should be enough, unless you change your auth login settings again for some reason),
  - allows the `functions-framework` dev server to add
  auth credentials to cabe.skia.org grpc requests
 - you'll get some cryptic errors about http 303 responses if you don't do this

In one terminal window, run the following:
```
functions-framework --target GetCabeAnalysis --debug
```
This should start up a local emulation of the cloud functions environment. It
should also log some diagnostic/debug info including the http port that it's
listening on. We'll assume that port is `8080` here.

In a second terminal window, run this command (the `-d` json payload is just
some example data; edit as necessary for your use case):
```
> curl localhost:8080 -X POST  -H "Content-Type: application/json"  -d '{"job_id":"10f98c20660000", "anomaly":{"chart":"AngularJS-TodoMVC"}}'
```

and it should print something like this to stdout:

```
{
  "statistic": {
    "control_median": 234.5450000010431,
    "lower": -0.5737619917789094,
    "p_value": 0.16015625,
    "treatment_median": 240.78499999977646,
    "upper": 4.42586858995615
  }
}
```

This should produce some output in both terminal windows, as well as generate
some server-side activity visible in the GCP console page for cabe.skia.org. The
request logs for the `cabeserver` container should also contain some evidence of it
handling the request from your local `functions-framework` devserver.
