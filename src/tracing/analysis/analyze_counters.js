// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.util');
base.require('ui');
base.require('tracing.trace_model.counter_sample');
base.exportTo('tracing.analysis', function() {

  var CounterSample = tracing.trace_model.CounterSample;

  function analyzeCounterSamples(results, allSamples) {
    var samplesByCounter = {};
    for (var i = 0; i < allSamples.length; i++) {
      var ctr = allSamples[i].series.counter;
      if (!samplesByCounter[ctr.guid])
        samplesByCounter[ctr.guid] = [];
      samplesByCounter[ctr.guid].push(allSamples[i]);
    }

    for (var guid in samplesByCounter) {
      var samples = samplesByCounter[guid];
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
    results.appendHeader('Selected counter:');
    var table = results.appendTable('analysis-counter-table', 2);
    results.appendInfoRow(table, 'Title', ctr.name);
    results.appendInfoRowTime(
        table, 'Timestamp', samplesWithSameTimestamp[0].timestamp);
    for (var i = 0; i < samplesWithSameTimestamp.length; i++) {
      var sample = samplesWithSameTimestamp[i];
      results.appendInfoRow(table, sample.series.name, sample.value);
    }
  }

  function analyzeMultipleCounterTimestamps(results, ctr, samplesByTimestamp) {
    results.appendHeader('Counter ' + ctr.name);
    var table = results.appendTable('analysis-counter-table', 2);

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
          null,
          null,
          samples.length,
          stats[i]);
    }
  }

  return {
    analyzeCounterSamples: analyzeCounterSamples,
    analyzeSingleCounterTimestamp: analyzeSingleCounterTimestamp,
    analyzeMultipleCounterTimestamps: analyzeMultipleCounterTimestamps
  };
});
