This branch contains a vulcanized build of catapult's trace viewer.

To update it:
```
  git checkout master
  REV=`git rev-parse HEAD`
  tracing/bin/vulcanize_trace_viewer
  cp tracing/bin/trace_viewer_full.html /tmp/
  git checkout vulcanized_traceviewer
  cp /tmp/trace_viewer_full.html .
  git add trace_viewer_full.html
  git commit -m "Update trace_viewer.html to $REV"
```
Then commit
