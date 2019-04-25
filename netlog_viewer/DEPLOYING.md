Deploying to appspot.com
============


Code is not automatically deployed to
[netlog-viewer.appspot.com](https://netlog-viewer.appspot.com/) once committed
to the repository. Rather, a release needs to be prepared and
deployed manually by an admin of the netlog-viewer appengine project:

1. Check out a clean copy of `catapult/netlog_viewer` (`master` branch).

2. Run the automated tests, `netlog_viewer/bin/run_dev_server_tests`, and
   confirm that (a) tests ran (b) were successful. (See caveat on
   [CONTRIBUTING](CONTRIBUTING.md) - headless tests may fail, in which case
   need to run them in non-headless mode.)

3. Authenticate with the `gcloud` command line tool. (Only needs to be done
   once.)
```
gcloud auth login
```

4. Build the vulcanized version that will be served by appengine.
```
netlog_viewer_build/build_for_appengine.py
```

5. Run the app server locally, load in browser, and do some basic sanity checks
   loading a net log file. Be sure to shift-reload so you aren't testing an old
   cached version, and also check that no JavaScript errors were logged to the
   console.

```
cd appengine
dev_appserver.py app.yaml
```

6. Deploy without making it the default version yet.
```
gcloud app deploy --no-promote --project netlog-viewer
```

7. Load the versioned URL that was printed in previous step, and again do some
   manual sanity checks.

8. Send live traffic to the new version using the
[GCP console](https://console.cloud.google.com/appengine/versions).
