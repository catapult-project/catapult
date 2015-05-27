<!-- Copyright 2015 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->
[![Build Status](https://travis-ci.org/google/trace-viewer.svg?branch=master)](https://travis-ci.org/google/trace-viewer)

![Trace Viewer Logo](https://raw.githubusercontent.com/google/trace-viewer/master/images/trace-viewer-circle-blue.png)

Trace-Viewer is the javascript frontend for Chrome [about:tracing](http://dev.chromium.org/developers/how-tos/trace-event-profiling-tool) and [Android
systrace](http://developer.android.com/tools/help/systrace.html).

It provides rich analysis and visualization capabilities for many types of trace
files. Its particularly good at viewing linux kernel traces (aka [ftrace](https://www.kernel.org/doc/Documentation/trace/ftrace.txt)) and Chrome's
[trace_event format](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU/preview). Trace viewer can be [embedded](https://github.com/google/trace-viewer/wiki/Embedding) as a component in your own code, or used from a plain checkout to turn trace files into standalone, emailable HTML files from the commandline:

    trace2html my_trace.json --output=my_trace.html && open my_trace.html

Its easy to [extend trace viewer](https://github.com/google/trace-viewer/wiki/ExtendingAndCustomizing) to support your favorite trace format, or add domain specific visualizations to the UI to simplify drilling down into complex data.

Contributing, quick version
===========================================================================
We welcome contributions! To hack on this code, from toplevel:
  ./run_dev_server

In any browser, navigate to
  http://localhost:8003/

Make sure tests pass before sending us changelist. **We use rietveld for codereview**. For more details, esp on rietveld, [read our contributing guide](https://github.com/google/trace-viewer/wiki/Contributing) or check out the [trace viewer wiki](https://github.com/google/trace-viewer/wiki).

Contact Us
===========================================================================
Join our Google Groups:
* [trace-viewer](https://groups.google.com/forum/#!forum/trace-viewer)
* [trace-viewer-bugs](https://groups.google.com/forum/#!forum/trace-viewer-bugs)
* [tracing@chromium.org](https://groups.google.com/a/chromium.org/forum/#!forum/tracing) (for c++ backend code)
