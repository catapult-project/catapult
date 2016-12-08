<!-- Copyright 2016 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->

# HistogramSet JSON Format

This document assumes familiarity with the concepts introduced in
[how-to-write-metrics](/docs/how-to-write-metrics.md).

HistogramSet JSON contains an unordered array of dictionaries, where each
dictionary represents either a Histogram or a Diagnostic.

```javascript
[
  {
    "name": "my amazing metric",
    "guid": "123e4567-e89b-12d3-a456-426655440000",
    "unit": "ms",
    "binBoundaries": [0, [0, 100, 10]],
    "shortName": "my metric",
    "description": "this is my awesome amazing metric",
    "diagnostics": {
      "iteration": "923e4567-e89b-12d3-a456-426655440000",
    },
    "sampleValues": [0, 1, 42, -999999999.99999, null],
    "maxNumSampleValues": 1000,
    "numNans": 1,
    "nanDiagnostics": [
      {
        "events": {
          "type": "RelatedEventSet",
          "events": [
            {
              "stableId": "a.b.c", "title": "Title", "start": 0, "duration": 1
            }
          ]
        }
      }
    ],
    "running": [5, 42, 0, -1, -999, -900, 100],
    "allBins": {
      "0": [1],
      "1": [1],
    },
    "summaryOptions": {
      "nans": true,
      "percentile": [0.5, 0.95, 0.99],
    },
  },
  {
    "guid": "923e4567-e89b-12d3-a456-426655440000",
    "type": "IterationInfo",
    "benchmarkName": "memory",
    "benchmarkStartMs": 1234567890,
    "label": "abc",
    "storyDisplayName": "my story",
    "storyGroupingKeys": {"state": "pre"},
    "storyRepeatCounter": 0,
    "storyUrl": "http://example.com/",
    "storysetRepeatCounter": 0,
  },
]
```

## Histograms

### Required fields

 * `name`: any string
 * `guid`: string UUID
 * `unit`: underscore-separated string of 1 or 2 parts:
    * The required unit base name must be one of
       * ms
       * tsMs
       * n%
       * sizeInBytes
       * J
       * W
       * unitless
       * count
       * sigma
    * Optional improvement direction must be one of
       * biggerIsBetter
       * smallerIsBetter

### Optional fields

 * `shortName`: any string
 * `description`: any string
 * `binBoundaries`: an array that describes how to build bin boundaries
   The first element must be a number that specifies the boundary between the
   underflow bin and the first central bin. Subsequent elements can be either
    * numbers specifying bin boundaries, or
    * arrays of 3 numbers that specify how to build sequences of bin boundaries:
       * The first of which is an enum:
          * 0 (LINEAR)
          * 1 (EXPONENTIAL)
       * The second number is the maximum bin boundary of the sequence.
       * The third and final number is the number of bin boundaries in the
         sequence.
   If `binBoundaries` is undefined, then the Histogram contains single bin whose
   range spans `-Number.MAX_VALUE` to `Number.MAX_VALUE`
 * `diagnostics`: a DiagnosticMap that pertains to the entire Histogram
   This can reference shared Diagnostics by `guid`.
 * `sampleValues`: array of sample values
 * `maxNumSampleValues`: maximum number of sample values
   If undefined, defaults to allBins.length * 10.
 * `numNans`: number of non-numeric samples added to the Histogram
 * `nanDiagnostics`: an array of DiagnosticMaps for non-numeric samples
 * `running`: an array of 7 numbers: count, max, meanlogs, mean, min, sum, variance
 * `allBins`: either an array of Bins or a dictionary mapping from index to Bin:
   A Bin is an array containing either 1 or 2 elements:
    * Required number bin count,
    * Optional array of sample DiagnosticMaps
 * `summaryOptions`: dictionary mapping from option names `avg, geometricMean,
   std, count, sum, min, max, nans` to boolean flags. The special option
   `percentile` is an array of numbers between 0 and 1. `summaryOptions`
   controls which statistics are produced as ScalarValues in telemetry and
   uploaded to the dashboard.

DiagnosticMap is a dictionary mapping strings to Diagnostic dictionaries.

## Diagnostics

The only field that is required for all Diagnostics, `type`, must be one of
 * `Generic`
 * `RelatedEventSet`
 * `Breakdown`
 * `RelatedValueSet`
 * `RelatedValueMap`
 * `RelatedHistogramBreakdown`
 * `IterationInfo`
 * `Scalar`

If a Diagnostic is in the root array of the JSON, then it is shared -- it may be
referenced by multiple Histograms. Shared Diagnostics must contain a string
field `guid` containing a UUID.

If a Diagnostic is contained in a Histogram, then it must not have a `guid`
field.

The other fields of Diagnostic dictionaries depend on `type`.

### IterationInfo

 * `benchmarkName`: string
 * `benchmarkStartMs`: number of ms since unix epoch
 * `label`: string
 * `legacyTIRLabel`: string
 * `storyDisplayName`: string
 * `storyGroupingKeys`: dictionary mapping from strings to strings
 * `storyRepeatCounter`: number
 * `storyUrl`: string
 * `storysetRepeatCounter`: number

### DeviceInfo

 * `chromeVersion`: string (to be moved from IterationInfo)
 * `osName`: one of
    * `mac`
    * `android`
    * `linux`
    * `chrome`
    * `win`
 * `osVersion`: string (to be moved from IterationInfo)
 * `arch`: not yet specified, but will contain bittiness (32-bit vs 64-bit)
 * `gpuInfo`: not yet specified, but will contain information about the GPU
 * `ram`: number of bytes of RAM

### BuildbotInfo

 * `masterName`: string
 * `slaveName`: string
 * `buildNumber`: number
 * `logUri`: string

### OwnershipInfo

 * `owners`: an array of strings containing email addresses

### Generic

 * `value`: can contain any JSON data.
