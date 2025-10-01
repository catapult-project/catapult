# DataStore to Skia export pipeline

# Set Up

Install the following packages:

```
pip install wheel
pip install 'apache-beam[gcp]'
```
# Development

First,

```
$ cd dashboard
```

You can run the following command to test Pipeline changes on Dataflow:

```
$ python skia_export/skia_upload.py \
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

The `--testing=yes` parameter ensures that no data is actually uploaded to GCS.
The job will be created and can be viewed in the [Dataflow Jobs
page](https://pantheon.corp.google.com/dataflow/jobs?src=ac&project=chromeperf).
It should have a name that looks like this:
`beamapp-eduardoyap-0427223019-644772-xkv7a4gk`. Instead of uploading, the
filename and skia_data will be logged, so that you can confirm the changes are
working as expected.

If you want to test changes on a particular timerange, add the following flags:

```
--start_time=202305270000 \
--end_time=202305280000
```
The string MUST be in YYYMMDDHHmm format.

If you want to run on a particular repo, use the following flag:
```
--repo_to_export=v8
```

# Updating Templates

Once your changes have been tested and merged. You need to update the template,
so that your changes are reflected in production. Run the following command:

```
$ python skia_export/skia_upload.py \
  --service_account_email=chromeperf@appspot.gserviceaccount.com  \
  --runner=DataflowRunner \
  --region=us-central1 \
  --setup_file=skia_export/setup.py \
  --project=chromeperf \
  --staging_location=gs://chromeperf-dataflow/staging \
  --temp_location=gs://chromeperf-dataflow/temp \
  --template_location=gs://chromeperf-dataflow/templates/skia_export
```

Do not change any of the parameters.

# Backfill Run

To backfill data at a particular timerange, you can run the following command:

```
$ gcloud dataflow jobs run export-skia-backfill \
  --service-account-email=chromeperf@appspot.gserviceaccount.com \
  --gcs-location=gs://chromeperf-dataflow/templates/skia_export \
  --disable-public-ips \
  --max-workers=70 \
  --region=us-central1 \
  --staging-location=gs://chromeperf-dataflow/staging \
  --subnetwork=regions/us-central1/subnetworks/dashboard-batch \
  --worker-machine-type=e2-standard-4 \
  --project=chromeperf \
  --parameters=start_time=202304250000,end_time=202304260000,repo_to_export=fuchsia
```

Make sure you set start_time and end_time to desired range in YYYYMMDDHH format.
