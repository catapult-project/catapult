// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('analysis.slice_analysis');

base.require('analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  function analyzeSingleSliceHit(results, sliceHit) {
    var slice = sliceHit.slice;
    var table = results.appendTable('analysis-slice-table', 2);

    results.appendTableHeader(table, 'Selected slice:');
    results.appendSummaryRow(table, 'Title', slice.title);

    if (slice.category)
      results.appendSummaryRow(table, 'Category', slice.category);

    results.appendSummaryRowTime(table, 'Start', slice.start);
    results.appendSummaryRowTime(table, 'Duration', slice.duration);

    if (slice.durationInUserTime) {
      results.appendSummaryRowTime(
          table, 'Duration (U)', slice.durationInUserTime);
    }

    var n = 0;
    for (var argName in slice.args) {
      n += 1;
    }
    if (n > 0) {
      results.appendSummaryRow(table, 'Args');
      for (var argName in slice.args) {
        var argVal = slice.args[argName];
        // TODO(sleffler) use span instead?
        results.appendSummaryRow(table, ' ' + argName, argVal);
      }
    }
  }

  function analyzeMultipleSliceHits(results, sliceHits) {
    var tsLo = sliceHits.bounds.min;
    var tsHi = sliceHits.bounds.max;

    // compute total sliceHits duration
    var titles = sliceHits.map(function(i) { return i.slice.title; });

    var numTitles = 0;
    var slicesByTitle = {};
    for (var i = 0; i < sliceHits.length; i++) {
      var slice = sliceHits[i].slice;
      if (!slicesByTitle[slice.title]) {
        slicesByTitle[slice.title] = {
          slices: []
        };
        numTitles++;
      }
      slicesByTitle[slice.title].slices.push(slice);
    }

    var table;
    table = results.appendTable('analysis-slices-table', 3);
    results.appendTableHeader(table, 'Slices:');

    var totalDuration = 0;
    for (var sliceGroupTitle in slicesByTitle) {
      var sliceGroup = slicesByTitle[sliceGroupTitle];
      var duration = 0;
      var avg = 0;
      var startOfFirstOccurrence = Number.MAX_VALUE;
      var startOfLastOccurrence = -Number.MAX_VALUE;
      var frequencyDetails = undefined;
      var min = Number.MAX_VALUE;
      var max = -Number.MAX_VALUE;
      for (var i = 0; i < sliceGroup.slices.length; i++) {
        duration += sliceGroup.slices[i].duration;
        startOfFirstOccurrence = Math.min(sliceGroup.slices[i].start,
                                          startOfFirstOccurrence);
        startOfLastOccurrence = Math.max(sliceGroup.slices[i].start,
            startOfLastOccurrence);
        min = Math.min(sliceGroup.slices[i].duration, min);
        max = Math.max(sliceGroup.slices[i].duration, max);
      }

      totalDuration += duration;

      if (sliceGroup.slices.length == 0)
        avg = 0;
      avg = duration / sliceGroup.slices.length;

      var details = {min: min,
        max: max,
        avg: avg,
        avg_stddev: undefined,
        frequency: undefined,
        frequency_stddev: undefined};

      // Compute the stddev of the slice durations.
      var sumOfSquaredDistancesToMean = 0;
      for (var i = 0; i < sliceGroup.slices.length; i++) {
        var signedDistance = details.avg - sliceGroup.slices[i].duration;
        sumOfSquaredDistancesToMean += signedDistance * signedDistance;
      }

      details.avg_stddev = Math.sqrt(
          sumOfSquaredDistancesToMean / (sliceGroup.slices.length - 1));

      // We require at least 3 samples to compute the stddev.
      var elapsed = startOfLastOccurrence - startOfFirstOccurrence;
      if (sliceGroup.slices.length > 2 && elapsed > 0) {
        var numDistances = sliceGroup.slices.length - 1;
        details.frequency = (1000 * numDistances) / elapsed;

        // Compute the stddev.
        sumOfSquaredDistancesToMean = 0;
        for (var i = 1; i < sliceGroup.slices.length; i++) {
          var currentFrequency = 1000 /
              (sliceGroup.slices[i].start - sliceGroup.slices[i - 1].start);
          var signedDistance = details.frequency - currentFrequency;
          sumOfSquaredDistancesToMean += signedDistance * signedDistance;
        }

        details.frequency_stddev = Math.sqrt(
            sumOfSquaredDistancesToMean / (numDistances - 1));
      }
      results.appendDataRow(
          table, sliceGroupTitle, duration, sliceGroup.slices.length,
          details);
    }
    results.appendDataRow(table, '*Totals', totalDuration, sliceHits.length);
    results.appendSpacingRow(table);
    results.appendSummaryRowTime(table, 'Selection start', tsLo);
    results.appendSummaryRowTime(table, 'Selection extent', tsHi - tsLo);
  }

  return {
    analyzeSingleSliceHit: analyzeSingleSliceHit,
    analyzeMultipleSliceHits: analyzeMultipleSliceHits
  };
});
