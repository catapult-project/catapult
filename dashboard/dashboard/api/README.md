# Perf dashboard API

## Authenticating
The perf dashboard API uses OAuth to authenticate. You must either have a
Google account or a service account to access the API. See examples directory
for examples of how to access the API.

## Alerts
URL patterns for accessing alerts:

 * `/api/alerts/bug_id/id`: Get all the alerts associated with bug `id`.
 * `/api/alerts/keys/comma_sep_list`: Get the alerts with the given list of
   keys, separated by commas.
 * `/api/alerts/rev/revision`: Get all the alerts with `revision` in the
   revision range. Note that `revision` should be the revision that is sent to
   the perf dashboard as the point ID; for ChromiumPerf it is the chromium
   commit pos; for v8 master it is the v8 commit pos.
 * `/api/alerts/history/N`: Get all the alerts for N days (defaults to 7).
   Can specify a `sheriff` param in postdata, defaults to `Chromium Perf
   Sheriff`. Can specify an `improvements` param equal to 1 to include
   improvements.
