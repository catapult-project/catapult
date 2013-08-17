// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.analysis.analyze_slices');

base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  function analyzeSingleSlice(results, slice) {
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

  function analyzeMultipleSlices(results, slices) {
    var tsLo = slices.bounds.min;
    var tsHi = slices.bounds.max;

    var numTitles = 0;
    var slicesByTitle = {};
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (slicesByTitle[slice.title] === undefined) {
        slicesByTitle[slice.title] = [];
        numTitles++;
      }
      var sliceGroup = slicesByTitle[slice.title];
      sliceGroup.push(slices[i]);
    }

    var table;
    table = results.appendTable('analysis-slices-table', 3);
    results.appendTableHeader(table, 'Slices:');

    var totalDuration = 0;
    base.iterItems(slicesByTitle,
        function(sliceGroupTitle, sliceGroup) {
          var duration = 0;
          var avg = 0;
          var startOfFirstOccurrence = Number.MAX_VALUE;
          var startOfLastOccurrence = -Number.MAX_VALUE;
          var frequencyDetails = undefined;
          var min = Number.MAX_VALUE;
          var max = -Number.MAX_VALUE;
          for (var i = 0; i < sliceGroup.length; i++) {
            var slice = sliceGroup[i];
            duration += slice.duration;
            startOfFirstOccurrence = Math.min(slice.start,
                startOfFirstOccurrence);
            startOfLastOccurrence = Math.max(slice.start,
                startOfLastOccurrence);
            min = Math.min(slice.duration, min);
            max = Math.max(slice.duration, max);
          }

          totalDuration += duration;

          if (sliceGroup.length == 0)
            avg = 0;
          avg = duration / sliceGroup.length;

          var statistics = {min: min,
            max: max,
            avg: avg,
            avg_stddev: undefined,
            frequency: undefined,
            frequency_stddev: undefined};

          // Compute the stddev of the slice durations.
          var sumOfSquaredDistancesToMean = 0;
          for (var i = 0; i < sliceGroup.length; i++) {
            var signedDistance =
                statistics.avg - sliceGroup[i].duration;
            sumOfSquaredDistancesToMean += signedDistance * signedDistance;
          }

          statistics.avg_stddev = Math.sqrt(
              sumOfSquaredDistancesToMean / (sliceGroup.length - 1));

          // We require at least 3 samples to compute the stddev.
          var elapsed = startOfLastOccurrence - startOfFirstOccurrence;
          if (sliceGroup.length > 2 && elapsed > 0) {
            var numDistances = sliceGroup.length - 1;
            statistics.frequency = (1000 * numDistances) / elapsed;

            // Compute the stddev.
            sumOfSquaredDistancesToMean = 0;
            for (var i = 1; i < sliceGroup.length; i++) {
              var currentFrequency = 1000 /
                  (sliceGroup[i].start -
                  sliceGroup[i - 1].start);
              var signedDistance = statistics.frequency - currentFrequency;
              sumOfSquaredDistancesToMean += signedDistance * signedDistance;
            }

            statistics.frequency_stddev = Math.sqrt(
                sumOfSquaredDistancesToMean / (numDistances - 1));
          }
          results.appendDataRow(
              table, sliceGroupTitle, duration, sliceGroup.length,
              statistics,
              function() {
                return new tracing.Selection(sliceGroup);
              });

          // The whole selection is a single type so list out the information
          // for each sub slice.
          if (numTitles === 1) {
            for (var i = 0; i < sliceGroup.length; i++) {
              analyzeSingleSlice(results, sliceGroup[i]);
            }
          }
        });

    // Only one row so we already know the totals.
    if (numTitles !== 1) {
      results.appendDataRow(table, '*Totals', totalDuration, slices.length);
      results.appendSpacingRow(table);
    }

    results.appendSummaryRowTime(table, 'Selection start', tsLo);
    results.appendSummaryRowTime(table, 'Selection extent', tsHi - tsLo);
  }

  return {
    analyzeSingleSlice: analyzeSingleSlice,
    analyzeMultipleSlices: analyzeMultipleSlices
  };
});
