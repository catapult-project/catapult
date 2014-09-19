Trace-Viewer is the javascript frontend for Chrome [about:tracing](http://dev.chromium.org/developers/how-tos/trace-event-profiling-tool) and [Android
systrace](http://developer.android.com/tools/help/systrace.html). It provides rich analysis and visualization capabilities for trace
files, supporting both the linux kernel trace format and Chrome's
base/trace_event.

Supported File formats
===========================================================================
 * [Trace Event Format](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU/edit?usp=sharing)
 * Linux kernel traces


Quick-start
===========================================================================
To work on this code, from toplevel
  ./run_dev_server

In any browser, navigate to
  http://localhost:8003/

Make sure tests pass before committing.


To help out with trace-viewer
===========================================================================
Check out the [trace-viewer wiki](https://github.com/google/trace-viewer/wiki).

