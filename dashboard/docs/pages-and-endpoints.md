# Pages and Endpoints

## Main public web pages and their query parameters.

**/**: View recent regressions and improvements.
 - *days*: Number of days to show anomalies (optional).
 - *sheriff*: Sheriff to show anomalies for (optional)
 - *num\_changes*: The number of improvements/regressions to list.

**/alerts**: View current outstanding alerts
 - *sheriff*: A sheriff rotation name, defaults to Chromium Perf Sheriff.
 - *triaged*: Whether to include recent already-triaged alerts.
 - *improvements*: Whether to include improvement alerts.
 - *sortby*: A field in the alerts table to sort rows by.
 - *sortdirection*: Direction to sort, either "up" or "down".

**/report**: Browse graphs and compare charts across platforms.
 - *sid*: A stored combination set of tests and graphs to view.
 - *masters*: Comma-separated list of master names
 - *bots*: Comma-separated list of bot names.
 - *tests*: Comma-separated list of test paths starting from benchmark name.
 - *rev*: Revision number (optional).
 - *num\_points*: Number of points to plot (optional).
 - *start\_rev*: Starting revision number (optional).
 - *end\_rev*: Ending revision number (optional).
 - *checked*: Series to check. Could be "core" (important + ref) or "all".

**/group\_report**: View graphs for a set of alerts
 - *bug\_id*: Bug ID to view alerts for.
 - *rev*: Chromium commit position to view alerts for.
 - *keys*: Comma-separated list URL-safe keys, each represents one alert

**/debug\_alert**: Experiment with the alerting function, or diagnose why and when an alert would occur at some place.
 - *test\_path*: Full test path (Master/bot/benchmark/...) to get points for.
 - *rev*: A revision to center the graph on.
 - *num\_before*: Number of points to fetch before rev.
 - *num\_after*: Number of points to fetch starting from rev.
 - *config*: JSON containing custom thresholds parameters.

**/new\_points**: View recently-added points for some set of tests, and verify whether or not data was received.
- *num\_points*: Max number of points to fetch.
- *pattern*: A test path pattern (Master/bot/benchmark/...) with wildcards to match.
- *max\_tests*: Maximum number of tests that match the pattern to fetch.

**/stats**: View and generate stats about alert volume.
 - *key*: URL-safe key of existing previously generated stats group.

**/bisect\_stats**: View bisect job success rate stats.

**/set\_warning\_message**: Set a warning message about outages and planned maintenance.

## Administrative pages

 - /change\_internal\_only
 - /edit\_anomaly\_configs
 - /edit\_bug\_labels
 - /edit\_sheriffs
 - /edit\_test\_owners
 - /load\_graph\_from\_prod
 - /migrate\_test\_names
 - /get\_logs

## XHR handlers

 - /associate\_alerts
 - /file\_bug
 - /edit\_anomalies
 - /graph\_json
 - /graph\_revisions
 - /list\_tests
 - /list\_monitored\_tests
 - /start\_try\_job
 - /graph\_csv
