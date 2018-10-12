# Rolling back from a broken deployment

If the current default version is broken,
search the [Activity log](https://console.cloud.google.com/home/activity?project=chromeperf)
for ' updated default'. The top hit should be the current version, and the next
hit should be the previous version.

## Rollback to the previous version

Find the target version in the [app engine versions
list](https://console.cloud.google.com/appengine/versions?project=chromeperf).
Select the checkbox next to it, and then hit the "Migrate Traffic" button.
