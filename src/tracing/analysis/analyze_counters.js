// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.util');
base.require('ui');
base.require('tracing.trace_model.counter_sample');
base.exportTo('tracing.analysis', function() {

  var CounterSample = tracing.trace_model.CounterSample;

  function analyzeCounterSampleHits(results, allHits) {
    var hitsByCounter = {};
    for (var i = 0; i < allHits.length; i++) {
      var ctr = allHits[i].counterSample.series.counter;
      if (!hitsByCounter[ctr.guid])
        hitsByCounter[ctr.guid] = [];
      hitsByCounter[ctr.guid].push(allHits[i]);
    }

    for (var guid in hitsByCounter) {
      var hits = hitsByCounter[guid];
      var samples = hits.map(function(hit) { return hit.counterSample; });
      var ctr = samples[0].series.counter;

      var timestampGroups = CounterSample.groupByTimestamp(samples);
      if (timestampGroups.length == 1)
        analyzeSingleCounterTimestamp(results, ctr, timestampGroups[0]);
      else
        analyzeMultipleCounterTimestamps(results, ctr, timestampGroups);
    }
  }

  function analyzeSingleCounterTimestamp(
      results, ctr, samplesWithSameTimestamp) {
    var table = results.appendTable('analysis-counter-table', 2);
    results.appendTableHeader(table, 'Selected counter:');
    results.appendSummaryRow(table, 'Title', ctr.name);
    results.appendSummaryRowTime(
        table, 'Timestamp', samplesWithSameTimestamp[0].timestamp);
    for (var i = 0; i < samplesWithSameTimestamp.length; i++) {
      var sample = samplesWithSameTimestamp[i];
      results.appendSummaryRow(table, sample.series.name,
                               sample.value);
    }
  }

  function analyzeMultipleCounterTimestamps(results, ctr, samplesByTimestamp) {
    var table = results.appendTable('analysis-counter-table', 2);
    results.appendTableHeader(table, 'Counter ' + ctr.name);

    var sampleIndices = [];
    for (var i = 0; i < samplesByTimestamp.length; i++)
      sampleIndices.push(samplesByTimestamp[i][0].getSampleIndex());

    var stats = ctr.getSampleStatistics(sampleIndices);
    for (var i = 0; i < stats.length; i++) {
      var samples = [];
      for (var k = 0; k < sampleIndices.length; ++k)
        samples.push(ctr.getSeries(i).getSample(sampleIndices[k]).value);

      results.appendDataRow(
          table,
          ctr.name + ': series(' + ctr.getSeries(i).name + ')',
          samples,
          samples.length,
          stats[i]);
    }
  }

  return {
    analyzeCounterSampleHits: analyzeCounterSampleHits,
    analyzeSingleCounterTimestamp: analyzeSingleCounterTimestamp,
    analyzeMultipleCounterTimestamps: analyzeMultipleCounterTimestamps
  };
});
