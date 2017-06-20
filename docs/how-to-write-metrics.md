<!-- Copyright 2016 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->

# How to Write Metrics

Timeline-Based Measurement v2 is a system for computing metrics from traces.

A TBM2 metric is a Javascript function that takes a trace Model and produces
Histograms.


## Coding Practices

Please follow the [Catapult Javascript style guide](/docs/style-guide.md) so
that the TBM2 maintainers can refactor your metric when we need to update the TBM2
API.

Please write a unit test for your metric.

If your metric computes information from the trace that may be of general use to
other metrics or the trace viewer UI, then the TBM2 maintainers may ask for your
help to generalize your innovation into a part of the Trace Model such as the
[UserModel](/tracing/tracing/model/user_model/user_model.html) or
[ModelHelpers](/tracing/tracing/model/helpers/chrome_browser_helper.html).

Use the dev server to develop and debug your metric.

 * Run `./bin/run_dev_server`
 * Navigate to
   [http://localhost:8003/tracing_examples/trace_viewer.html](http://localhost:8003/tracing_examples/trace_viewer.html).
 * Open a trace that your metric can be computed from.
 * Open the Metrics side panel on the right.
 * Select your metric from the drop-down.
 * Inspect the results and change your metric if necessary.
 * Open different traces to explore corner cases in your metric.


## Trace Model

Trace logs are JSON files produced by tracing systems in Chrome, Android, linux
perf, BattOr, etc. The trace model is an object-level representation of events
parsed from a trace log. The trace model contains Javascript objects
representing

 * OS [processes](/tracing/tracing/model/process.html),
   [threads](/tracing/tracing/model/thread.html),
 * utilities for finding special processes and threads such as
   [ChromeBrowserHelper](/tracing/tracing/model/helpers/chrome_browser_helper.html),
 * synchronous [ThreadSlices](/tracing/tracing/model/thread_slice.html)
   and asynchronous [AsyncSlices](/tracing/tracing/model/async_slice.html),
 * [snapshots](/tracing/tracing/model/object_snapshot.html) of object state as it changes throughout time,
 * [RPCs](/tracing/tracing/model/flow_event.html),
 * [FrameBlameContexts](/tracing/tracing/extras/chrome/blame_context/blame_context.html),
 * battery [power samples](/tracing/tracing/model/power_sample.html),
 * synthetic higher-level abstractions representing complex sets of
   events such as
   [UserExpectations](/tracing/tracing/model/user_model/user_expectation.html),
 * and [more](/tracing/tracing/model/model.html)!


## Histograms

A [Histogram](/tracing/tracing/value/histogram.html) is basically a common
[histogram](https://en.wikipedia.org/wiki/Histogram), but with a few extra bells
and whistles that are particularly useful for TBM2 metrics.

 * Specify units of samples and improvement direction with
   [Unit](/tracing/tracing/value/unit.html)
 * JSON serialization with asDict()/fromDict()
 * Build custom bin boundaries with HistogramBinBoundaries
 * Underflow and overflow bins for samples outside of the range of the central
   bins
 * Compute statistics such as average, stddev, sum, and percentiles
 * Customize which statistics are serialized with customizeSummaryOptions()
 * Count non-numeric samples
 * Store a random subset of sample values
 * getDifferenceSignificance() computes whether two histograms are significantly
   different with a Mann-Whitney U hypothesis test
 * addHistogram() merges two Histograms with the same units and bin boundaries

But the most complex special feature of Histograms is their Diagnostics.


## Diagnostics

When a metric significantly regresses, you then need to diagnose why it
regressed. Diagnostics are pieces of information that metrics attach to
Histograms in order help you diagnose regressions. Diagnostics may be associated
either with the entire Histogram directly, or with a particular sample.

Attach a Diagnostic to a Histogram:

```javascript
histogram.diagnostics.set('name', diagnostic)
// or
histograms.addHistogram(histogram, {name: diagnostic})
```

Attach a Diagnostic to all Histograms in a HistogramSet:

```javascript
histograms.addSharedDiagnostic(name, diagnostic);
```

Attach a Diagnostic to a sample:

```javascript
histogram.addSample(number, {name: diagnostic})
```

### General Diagnostics

 * [Generic](/tracing/tracing/value/diagnostics/generic.html): This can contain
   any data that can be serialized and deserialized using JSON.stringify() and
   JSON.parse(), including numbers, strings, Arrays, and dictionaries (simple
   Objects). It will be visualized using
   [generic-object-view](/tracing/tracing/ui/analysis/generic_object_view.html),
   which is quite smart about displaying tabular data using tables, URLs using
   HTML anchor tags, pretty-printing, recursive data structures, and more.
   ![](/docs/images/how-to-write-metrics-generic.png)
 * [Breakdown](/tracing/tracing/value/diagnostics/breakdown.html):
   Structurally, these are Maps from strings to numbers. Conceptually, they
   describe what fraction of a whole (either a Histogram or a sample) is due to
   some sort of category - either a category of event, CPU sample, memory
   consumer, whathaveyou. Visually, they are a stacked bar chart with a single
   bar, which is spiritually a pie chart, but less misleading.
   ![](/docs/images/how-to-write-metrics-breakdown.png)
 * [RelatedEventSet](/tracing/tracing/value/diagnostics/related_event_set.html):
   This is a Set of references to Events in the trace model. Visually, they
   are displayed as HTML links which, when clicked in the metrics-side-panel,
   select the referenced Events in the trace viewer's timeline view. When
   clicked in results2.html, they currently do nothing, but should eventually
   open the trace that contains the events and select them.
   ![](/docs/images/how-to-write-metrics-related-event-set.png)
 * [DateRange](/tracing/tracing/value/diagnostics/date_range.html):
   This is a Range of Dates. It cannot be empty, but the minDate could be the
   same as the maxDate. Telemetry automatically adds 2 shared DateRanges to all
   results: 'benchmark start' and 'trace start'.
   ![](/docs/images/how-to-write-metrics-date-range.png)

### Histogram Relationship Diagnostics

 * [RelatedHistogramSet](/tracing/tracing/value/diagnostics/related_histogram_set.html):
   These are Sets of references to other Histograms. Visually, they are a set
   of HTML links which, when clicked, select the contained Histograms. The text
   content of the HTML link is the name of the referenced Histogram.
   ![](/docs/images/how-to-write-metrics-related-histogram-set.png)
 * [RelatedHistogramMap](/tracing/tracing/value/diagnostics/related_histogram_map.html):
   These are Maps from strings to references to other Histograms. Visually, they
   are a set of HTML links similar to RelatedHistogramSet, but the text content of
   the link is the Map's string key instead of the Histogram's name. One example
   application is when a Histogram was produced not directly by a metric, but
   rather by merging together other Histograms, then it will have a
   RelatedHistogramMap named 'merged from' that refers to the Histograms that were
   merged by their grouping key, e.g. the telemetry story name.
   ![](/docs/images/how-to-write-metrics-related-histogram-map.png)
 * [RelatedHistogramBreakdown](/tracing/tracing/value/diagnostics/related_histogram_breakdown.html):
   Structurally, this is a RelatedHistogramMap, but conceptually and visually, this
   is a Breakdown. Whereas Breakdown's stacked bar chart derives its data from
   the numbers contained explicitly in the Breakdown, a
   RelatedHistogramBreakdown's stacked
   bar chart derives its data from the referenced Histograms' sums.
   ![](/docs/images/how-to-write-metrics-related-histogram-breakdown.png)

### Environment Information Diagnostics

 * [TelemetryInfo](/tracing/tracing/value/diagnostics/telemetry_info.html):
   This is automatically attached to every Histogram produced by telemetry.
   Structurally, it's a class with explicit named fields.
   Conceptually, it contains information about the origins of the trace that was
   consumed by the metric that produced the Histogram, such as the benchmark
   name, story name, benchmark start timestamp, etc.
   Visually, TelemetryInfos are displayed as a table.
   ![](/docs/images/how-to-write-metrics-telemetry.png)
 * [DeviceInfo](/tracing/tracing/value/diagnostics/device_info.html):
   This is automatically attached to every Histogram produced by buildbots.
   Structurally, it's a class with explicit named fields. Conceptually, it
   contains information about the machine that produced the trace that was
   consumed by the metric that produced the Histogram, such as the OS version,
   Chrome version, etc. Visually, DeviceInfos are displayed as a table.
   ![](/docs/images/how-to-write-metrics-device.png)
 * [RevisionInfo](/tracing/tracing/value/diagnostics/revision_info.html):
   This is automatically attached to every Histogram produced by telemetry.
   Structurally, it's a class with explicit named fields. Conceptually, it
   contains ranges of revisions of the software used to produce the trace that
   was consumed by the metric that produced the Histogram, such as the Chromium
   revision, v8 revision, and catapult revision. Visually, RevisionInfos are
   displayed as a table.
   ![](/docs/images/how-to-write-metrics-revision.png)
 * [BuildbotInfo](/tracing/tracing/value/diagnostics/buildbot_info.html):
   This is automatically attached to every Histogram produced by Chrome's
   performance testing buildbots. Structurally, it's a class with explicit named
   fields. Conceptually, it contains information about the buildbot process that
   ran telemetry. Visually, it is displayed as a table.
   ![](/docs/images/how-to-write-metrics-buildbot.png)

### Other Diagnostics

 * [Scalar](/tracing/tracing/value/diagnostics/scalar.html):
   Metrics must not use this, since it is incapable of being merged. It is
   mentioned here for completeness. It wraps a Scalar, which is just a
   unitted number. This is only to allow Histograms in other parts of the trace
   viewer to display number sample diagnostics more intelligently than Generic
   can. If a metric wants to display number sample diagnostics intelligently,
   then it should use RelatedHistogramSet or RelatedHistogramMap; if it does not want to
   monitor changes in those numbers, then the TBM2 maintainers can add a
   HistogramDiagnostic that supports merging.


## Consumers of Histograms

Histograms are consumed by

 * [histogram-set-table](/tracing/tracing/value/ui/histogram_set_table.html) in
   both results2.html and the Metrics side panel in trace viewer,
 * the [dashboard](https://chromeperf.appspot.com) indirectly via their statistics.

Currently, telemetry discards Histograms and Diagnostics, and only passes their
statistics scalars to the dashboard. Histograms and their Diagnostics will be
passed directly to the dashboard early 2017.

Metrics can control which statistics are uploaded to the dashboard by passing a
dictionary to customizeSummaryOptions() to enable or disable statistics. The
default options are as follows:

 * `avg` (average/mean): true
 * `geometricMean`: false
 * `std` (standard deviation): true
 * `count` (number of samples): true
 * `sum`: true
 * `min`: true
 * `max`: true
 * `nans` (number of non-numeric samples): false
 * `percentile`: []
   * Unlike the other options which are booleans, percentile is an array of
     numbers between 0 and 1. In order to upload the median, for example, a
     metric would call `histogram.customizeSummaryOptions({percentile: [0.5]})`.


## How histogram-set-table Uses Merging and TelemetryInfo

The histogram-set-table element uses the fields of TelemetryInfo, along with the
merging capabilities of Histograms, to allow dynamic, hierarchical
organization of histograms:

* TelemetryInfo has mostly string/number (story name, story/set repeat count,
  etc.) fields and one dict field that specifies the names of any story grouping
  keys together with their histogram.
* After loading histograms, histogram-set-table computes categories to be
  displayed by the groupby picker at the top of the UI:
  * Categories are fields of TelemetryInfo that have more than one value across
    all histograms in the HistogramSet.
  * Instead of having one category for all story grouping keys, each grouping
    individual grouping key may be listed as a category. For example, in Page
    Cycler v2 benchmarks, the "cache_temperature" grouping key would be
    displayed as a category.
* Choosing groups builds a hierarchy of histograms that is filled in by merging
  histograms from the bottom up. Expanding the rows of histogram-set-table, any
  leaf nodes are histograms that were loaded, and their ancestors are computed by
  merging.
* histogram-set-table uses the "label" property of TelemetryInfo to define the
  columns of the table.
