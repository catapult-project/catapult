# DataStore to Skia Export Pipeline

This document describes the pipeline for exporting data from Cloud Datastore to Skia's performance analysis tools.

## Set Up

Install the required Python packages:

```bash
pip install wheel
pip install 'apache-beam[gcp]'
```

## Development

All development commands should be run from the `dashboard` directory:

```bash
cd dashboard
```

### Testing Pipeline Changes

You can run the following command to test Pipeline changes on Dataflow:

```bash
python skia_export/skia_upload.py \
  --service_account_email=chromeperf@appspot.gserviceaccount.com \
  --runner=DataflowRunner \
  --region=us-central1 \
  --temp_location=gs://chromeperf-dataflow/temp  \
  --subnetwork=regions/us-central1/subnetworks/dashboard-batch \
  --num_workers=70 \
  --setup_file=skia_export/setup.py \
  --no_use_public_ips \
  --testing=yes
```

The `--testing=yes` parameter ensures that no data is actually uploaded to GCS. The job will be created and can be viewed in the [Dataflow Jobs page](https://pantheon.corp.google.com/dataflow/jobs?src=ac&project=chromeperf). It should have a name that looks like this: `beamapp-eduardoyap-0427223019-644772-xkv7a4gk`. Instead of uploading, the filename and `skia_data` will be logged, so that you can confirm the changes are working as expected.

### Testing on a Specific Time Range

If you want to test changes on a particular time range, add the following flags:

```bash
--start_time=202305270000 \
--end_time=202305280000
```

The string MUST be in `YYYYMMDDHHmm` format.

### Testing on a Specific Repository

If you want to run on a particular repo, use the following flag:

```bash
--repo_to_export=v8
```

### Testing on a Specific Bot or Benchmark

To narrow down your test to a specific bot or benchmark, you can use the following flags. This is useful for debugging data from a particular test configuration.

For filtering by bot:

```bash
--bot_to_filter=linux-perf
```

For filtering by benchmark:
```bash
--benchmark_to_filter=speedometer
```

You can use these flags in combination with the time range and repository filters.

## Updating Templates

Once your changes have been tested and merged, you need to update the Dataflow template so that your changes are reflected in production. Run the following command:

```bash
python skia_export/skia_upload.py \
  --service_account_email=chromeperf@appspot.gserviceaccount.com  \
  --runner=DataflowRunner \
  --region=us-central1 \
  --setup_file=skia_export/setup.py \
  --project=chromeperf \
  --staging_location=gs://chromeperf-dataflow/staging \
  --temp_location=gs://chromeperf-dataflow/temp \
  --template_location=gs://chromeperf-dataflow/templates/skia_export
```

**Do not change any of the parameters in this command.**

## Backfill Run

To backfill data for a particular time range, you can run the following command:

```bash
gcloud dataflow jobs run export-skia-backfill \
  --service-account-email=chromeperf@appspot.gserviceaccount.com \
  --gcs-location=gs://chromeperf-dataflow/templates/skia_export \
  --disable-public-ips \
  --max-workers=70 \
  --region=us-central1 \
  --staging-location=gs://chromeperf-dataflow/staging \
  --subnetwork=regions/us-central1/subnetworks/dashboard-batch \
  --worker-machine-type=e2-standard-4 \
  --project=chromeperf \
  --parameters=start_time=202304250000,end_time=202304260000,repo_to_export=fuchsia,bot_to_filter=linux-perf
```

Make sure you set `start_time` and `end_time` to the desired range in `YYYYMMDDHHmm` format. You can also specify `repo_to_export`, `bot_to_filter`, and `benchmark_to_filter` as needed.
