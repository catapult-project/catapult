// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  function analyzeSingleCounterSampleHit(results, counterSampleHit) {
    var ctr = counterSampleHit.counter;
    var sampleIndex = counterSampleHit.sampleIndex;

    var values = [];
    for (var i = 0; i < ctr.numSeries; ++i)
      values.push(ctr.getSeries(i).getSample(sampleIndex).value);

    var table = results.appendTable('analysis-counter-table', 2);
    results.appendTableHeader(table, 'Selected counter:');
    results.appendSummaryRow(table, 'Title', ctr.name);
    results.appendSummaryRowTime(
        table, 'Timestamp', ctr.timestamps[sampleIndex]);

    for (var i = 0; i < ctr.numSeries; i++)
      results.appendSummaryRow(table, ctr.getSeries(i).name, values[i]);
  }

  function analyzeMultipleCounterSampleHits(results, counterSampleHits) {
    var hitsByCounter = {};
    for (var i = 0; i < counterSampleHits.length; i++) {
      var ctr = counterSampleHits[i].counter;
      if (!hitsByCounter[ctr.guid])
        hitsByCounter[ctr.guid] = [];
      hitsByCounter[ctr.guid].push(counterSampleHits[i]);
    }

    var table = results.appendTable('analysis-counter-table', 2);
    results.appendTableHeader(table, 'Counters:');
    for (var id in hitsByCounter) {
      var hits = hitsByCounter[id];
      var ctr = hits[0].counter;

      var sampleIndices = [];
      for (var i = 0; i < hits.length; i++)
        sampleIndices.push(hits[i].sampleIndex);

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
  }

  return {
    analyzeSingleCounterSampleHit: analyzeSingleCounterSampleHit,
    analyzeMultipleCounterSampleHits: analyzeMultipleCounterSampleHits
  };
});
