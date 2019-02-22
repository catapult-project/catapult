The next version of the Chromeperf Dashboard is at the prototype stage,
available for preview at https://v2spa-dot-chromeperf.appspot.com .

In order to develop or deploy v2spa, a one-time setup is required:
```
cd dashboard
ln -sf ../devil/devil/
ln -sf ../third_party/apiclient/apiclient/
ln -sf ../third_party/apiclient/googleapiclient/
ln -sf ../third_party/cloudstorage/
ln -sf ../third_party/flot/
ln -sf ../third_party/gae_ts_mon/
ln -sf ../third_party/httplib2/httplib2/
ln -sf ../third_party/jquery/
ln -sf ../third_party/oauth2client/oauth2client/
ln -sf ../third_party/polymer
ln -sf ../third_party/polymer-svg-template/
ln -sf ../third_party/polymer/components/
ln -sf ../third_party/polymer2/
ln -sf ../third_party/polymer2/bower_components/
ln -sf ../third_party/redux/
ln -sf ../third_party/redux/redux.min.js
ln -sf ../third_party/six/
ln -sf ../third_party/uritemplate/uritemplate/
ln -sf ../tracing/third_party/gl-matrix/dist/gl-matrix-min.js
ln -sf ../tracing/third_party/mannwhitneyu/
ln -sf ../tracing/tracing
ln -sf ../tracing/tracing_build/
ln -sf ../tracing/tracing_project.py
ln -sf /usr/lib/python2.7/dist-packages/jinja2/
ln -sf /usr/lib/python2.7/dist-packages/markupsafe/
```

Checkout the `v2spa` branch.

In order to deploy v2spa to v2spa-dot-chromeperf.appspot.com, run
`dashboard/bin/deploy`. That serves a vulcanized HTML file at `/` and the
same script request handlers as V1, which is configured in app.yaml and
continues to be deployed to chromeperf.appspot.com by `dashboard/bin/deploy`.

In order to develop v2spa locally, run `dev_appserver.py v2spa_dev.yaml` to
serve the unvulcanized sources at http://localhost:8080 to speed up reloading
changes. `v2spa_dev.yaml` is not intended to be deployed even to a dev instance.
When running on localhost, V2SPA does not send requests to the backend, so no
script request handlers are needed.
