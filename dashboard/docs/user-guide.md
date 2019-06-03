# Chromeperf User Guide (Single Page App)

The next version of the Chromeperf dashboard is currently available at
[v2spa-dot-chromeperf.appspot.com](https://v2spa-dot-chromeperf.appspot.com) but
will soon replace the [main page](https://chromeperf.appspot.com).
All other existing pages will remain in place for a while. The SPA links to the
old pages in the top right corner, and the old alerts, report, and group_report
pages link to the SPA at the top.

Please [file a bug](https://bugs.chromium.org/p/chromium/issues/entry?description=Question+for+the+user+guide:%A0&components=Speed%3EDashboard&labels=chromeperf2)
if you have any questions that are not addressed here.

## Sign in

Click the red account icon in the top right corner to sign in with Google.
This is required in order to modify alerts and access internal-only data.

## Reports

(This section coming soon.)

## Alerts

Add an Alerts section to the SPA by clicking the '+' bell icon labelled 'New
alerts section' in the drawer on the left. Multiple Alerts sections may be
added to the SPA.

### Alerts Sources

Select a source of alerts by either selecting a Sheriff, Bug, or Report.

There are two switches to the right of the Sheriff/Bug/Report menus.
When the first switch displays "Regressions Only", it is hiding
improvements. Click it to switch it to "Regressions and improvements" to display
both.
When the second switch displays "New Only", it is hiding triaged alerts. Click
it to switch it to "New and Triaged" to display both.
You can also hover over these switches for explanation tooltips.

Untriaged alerts are loaded first, followed by triaged alerts to help you assign
new alerts to existing bugs.
You can start triaging new alerts without waiting for all triaged alerts to
finish loading.

### Alerts Table

Select alerts using the checkboxes in the table in order to preview their
history in the chart below the table. When a group of alerts is collapsed
(default), only the first alert in the group is displayed. Checking its checkbox
will select all untriaged alerts in the group. In order to select individual
alerts within groups, you can expand the group by clicking the expand button
(down arrow with number) on the left in the 'Count' column. In order to see
relevant triaged alerts, you can expand them by clicking the expand button (down
arrow with number) in the 'Triaged' column.

### Triaging

The four buttons at the top of the alerts table allow triaging alerts.
 * 'New Bug' opens a dialog. Configure the bug's Summary, Owner, CC,
   Description, labels, and component, then click Submit to file a new bug on
   crbug.com and assign selected alerts to it. If possible, a Pinpoint job is
   automatically started to bisect the revision range to find culprits.
 * 'Existing Bug' opens a dialog with an input, a switch, and a table of bugs.
   When the switch displays "Intersecting Bugs Only", the table only displays
   performance regression bugs containing alerts whose revision range overlaps
   that of the selected alerts. When the switch displays "All Bugs", the table
   displays the 100 most recent performance regression bugs regardless of
   revision range. Click a bug number in the left column to copy it to the
   input, or type the number of any existing bug, then click Submit to assign
   the selected alerts to that bug.
 * 'Ignore' does not open a dialog. It immediately ignores all selected alerts.
 * 'Unassign' is only active when triaged alerts are selected. It does not open
   a dialog. It immediately unassigns selected alerts so that they may be
   assigned to a different bug.

### Timeseries Charts

When alerts are selected, their timeseries are displayed in the chart below the
table. If more than 10 alerts are selected, only the first 10 timeseries are
displayed. In order to display timeseries for specific alerts, click the text in
their Suite, Measurement, Bot, or Case. That text is color-coded to match the
corresponding line in the chart.

See the following section for more information about how to use charts.

## Charts

Add a Chart section to the SPA by clicking the zig-zag icon labelled 'New Chart'
in the drawer on the left. Multiple Chart sections may be added to the SPA.

### Selecting Timeseries

In order to display timeseries charts, at least one Suite, Measurement, Bot, and
Statistic must be selected. Multiple Suites, Measurements, Bots, Cases, and
Statistics may be selected. Each selected Measurement and Statistic is always
displayed in separate lines, but Suites, Bots, and Cases may be Aggregated into
a single line or split into separate lines by checking or unchecking the
checkboxes below them.

At least one Suite must be selected before any Measurements, Bots, or Cases can
be selected. It should only take a fraction of a second to load the Measurement,
Bot, and Case options once a Suite is selected.

The Suite, Measurement, Bot, and Case menus each contain a 'Recommended'
section containing options that you have recently selected on this client. These
options are duplicated from their normal place in the full list of options.

The Case menu may also contain a 'Tags' section on the left of the full list of
options. See telemetry's story tags feature for more information.

The Measurement menu may also contain a 'Memory' section to better support
selecting memory measurements for the test suites that support them.

All menus may contain grouped options. For example, if a menu contains options
"a:b" and "a:c", then they will be grouped under a single top-level option "a".
Click the expand button (down arrow with number) on the left to show options "b"
and "c" grouped under "a".
Checking the checkbox for "a" selects both "a:b" and "a:c".
If "a" is also an option in addition to "a:b" and "a:c", then clicking the
checkbox for "a" will cycle through selecting all three options, or only "a", or
deselecting all three options.

Once at least one Suite, Measurement, Bot, and Statistic are selected, the
timeseries data is fetched from the datastore, optionally aggregated, and
displayed in the chart. The various parts of the chart are described below.

### Display Options

Click the gear icon to the left of the minimap in order to access the display
options.

 * Link or unlink these options to any other charts on the page.
 * Switch between Floating Y-Axis or Zero Y-Axis
 * Switch between Fixed X-Axis or True X-Axis
 * Select the mode:
    * Normalize per unit (default) normalizes lines with the same unit together,
      separately from lines with different units.
    * Normalize per line normalizes each line separately.
    * Center. Try it!
    * Delta. Try it!

### Minimap

The full history of only the first line is displayed here. Drag the grey brush
handles to select a revision range to display in the main chart.

### Main chart

Hover inside this chart to display a tooltip containing information about the
nearest data point. Unlike in the old charts, these tooltips are not
interactive. They are purely informational.

Click to display interactive details for the nearest data point.
Drag the grey brush handles to merge details for multiple consecutive data
points into a single column in the details table. See the 'Details Table'
section below.
Control/Command+Click to display interactive details for the nearest data point
in addition to all previously selected data points.
Click again within a brushed revision range to clear all brushed revision
ranges.

### Legend

When multiple lines are displayed in the chart, the legend is displayed to the
right of the minimap and main chart. Hover over a legend entry to bold the
corresponding line in the chart to make it easier to distinguish. Click a legend
entry to hide all other lines. Click it again to show them again.

### Details Table

When data points in the main chart are selected by clicking them, this table
loads all available data about the selected data points.

### Sparklines

When Aggregating multiple Suites, Bots, or Cases, tabs for these menus are
displayed below the details table. Sparkline tabs are also displayed for
memory Processes and Components. Sparklines will eventually be displayed for all
Measurements that upload RelatedNameMap Diagnostics.

Click a tab to display sparkline tiles. These tiles display the name of the
individual Suite, Measurement, Bot, or Case for the sparkline, and a small
chart.
Click a tile in order to open a new Chart section to explore that data.

Sparklines are not yet available for the chart-compound in Alerts sections.

## How to Start a Bisect

1. If not already signed in, click the red account icon in the top right corner
   to sign in with Google.
2. If not already looking at a chart, click the New Chart button in the drawer
   on the left and select the Suite, Measurement, Bot, and optionally Case and
   Statistic.
3. If the Details Table is not already displayed below the chart, click in the
   chart to select a data point at the desired revision range.
4. Click the BISECT button at the bottom of the Details Table below the chart.
5. Review the options in the Bisect dialog and click START.
