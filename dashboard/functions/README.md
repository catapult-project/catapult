# Cloud Functions

This directory hosts the source code for production Cloud Functions in the chromeperf project.

# How To Deploy Functions
To manually deploy all functions in this library, call:

```
gcloud builds submit --region=us-central1 --config cloudbuild.yaml .
```

This will execute cloudbuild.yaml and will deploy all functions in parallel.
