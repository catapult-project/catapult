# How To Deploy Workflows
To manually deploy all functions in this library, call:

```
gcloud builds submit --region=us-central1 --config cloudbuild.yaml .
```

This will execute cloudbuild.yaml and will deploy all workflows in parallel.
