// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.analysis.analyze_slices');

base.require('tracing.analysis.util');
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
    var sliceHitsByTitle = {};
    for (var i = 0; i < sliceHits.length; i++) {
      var slice = sliceHits[i].slice;
      if (!sliceHitsByTitle[slice.title]) {
        sliceHitsByTitle[slice.title] = {
          hits: []
        };
        numTitles++;
      }
      var sliceGroup = sliceHitsByTitle[slice.title];
      sliceGroup.hits.push(sliceHits[i]);
    }

    var table;
    table = results.appendTable('analysis-slices-table', 3);
    results.appendTableHeader(table, 'Slices:');

    var totalDuration = 0;
    base.iterItems(sliceHitsByTitle,
        function(sliceHitGroupTitle, sliceHitGroup) {
          var duration = 0;
          var avg = 0;
          var startOfFirstOccurrence = Number.MAX_VALUE;
          var startOfLastOccurrence = -Number.MAX_VALUE;
          var frequencyDetails = undefined;
          var min = Number.MAX_VALUE;
          var max = -Number.MAX_VALUE;
          for (var i = 0; i < sliceHitGroup.hits.length; i++) {
            var slice = sliceHitGroup.hits[i].slice;
            duration += slice.duration;
            startOfFirstOccurrence = Math.min(slice.start,
                startOfFirstOccurrence);
            startOfLastOccurrence = Math.max(slice.start,
                startOfLastOccurrence);
            min = Math.min(slice.duration, min);
            max = Math.max(slice.duration, max);
          }

          totalDuration += duration;

          if (sliceHitGroup.hits.length == 0)
            avg = 0;
          avg = duration / sliceHitGroup.hits.length;

          var statistics = {min: min,
            max: max,
            avg: avg,
            avg_stddev: undefined,
            frequency: undefined,
            frequency_stddev: undefined};

          // Compute the stddev of the slice durations.
          var sumOfSquaredDistancesToMean = 0;
          for (var i = 0; i < sliceHitGroup.hits.length; i++) {
            var signedDistance =
                statistics.avg - sliceHitGroup.hits[i].slice.duration;
            sumOfSquaredDistancesToMean += signedDistance * signedDistance;
          }

          statistics.avg_stddev = Math.sqrt(
              sumOfSquaredDistancesToMean / (sliceHitGroup.hits.length - 1));

          // We require at least 3 samples to compute the stddev.
          var elapsed = startOfLastOccurrence - startOfFirstOccurrence;
          if (sliceHitGroup.hits.length > 2 && elapsed > 0) {
            var numDistances = sliceHitGroup.hits.length - 1;
            statistics.frequency = (1000 * numDistances) / elapsed;

            // Compute the stddev.
            sumOfSquaredDistancesToMean = 0;
            for (var i = 1; i < sliceHitGroup.hits.length; i++) {
              var currentFrequency = 1000 /
                  (sliceHitGroup.hits[i].slice.start -
                  sliceHitGroup.hits[i - 1].slice.start);
              var signedDistance = statistics.frequency - currentFrequency;
              sumOfSquaredDistancesToMean += signedDistance * signedDistance;
            }

            statistics.frequency_stddev = Math.sqrt(
                sumOfSquaredDistancesToMean / (numDistances - 1));
          }
          results.appendDataRow(
              table, sliceHitGroupTitle, duration, sliceHitGroup.hits.length,
              statistics,
              function() {
                return new tracing.Selection(sliceHitGroup.hits);
              });

          // The whole selection is a single type so list out the information
          // for each sub slice.
          if (numTitles === 1) {
            for (var i = 0; i < sliceHitGroup.hits.length; i++) {
              analyzeSingleSliceHit(results, sliceHitGroup.hits[i]);
            }
          }
        });

    // Only one row so we already know the totals.
    if (numTitles !== 1) {
      results.appendDataRow(table, '*Totals', totalDuration, sliceHits.length);
      results.appendSpacingRow(table);
    }

    results.appendSummaryRowTime(table, 'Selection start', tsLo);
    results.appendSummaryRowTime(table, 'Selection extent', tsHi - tsLo);
  }

  return {
    analyzeSingleSliceHit: analyzeSingleSliceHit,
    analyzeMultipleSliceHits: analyzeMultipleSliceHits
  };
});
