// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.importer.trace_event_importer');

'use strict';

base.unittest.testSuite('tracing.timeline_track_view', function() {
  var NoCountersFilter = function() {
  };

  NoCountersFilter.prototype = {
    __proto__: tracing.Filter.prototype,
    matchCounter: function(c) {
      return false;
    }
  };

  var NoCpusFilter = function() {
  };

  NoCpusFilter.prototype = {
    __proto__: tracing.Filter.prototype,
    matchCpu: function(c) {
      return false;
    }
  };

  var NoProcessesFilter = function() {
  };

  NoProcessesFilter.prototype = {
    __proto__: tracing.Filter.prototype,
    matchProcess: function(c) {
      return false;
    }
  };

  var NoThreadsFilter = function() {
  };

  NoThreadsFilter.prototype = {
    __proto__: tracing.Filter.prototype,
    matchThread: function(c) {
      return false;
    }
  };

  test('instantiate', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'b', args: {}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'E'}
    ];
    var model = new tracing.TraceModel(events);
    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;
    timeline.focusElement = timeline;
    timeline.tabIndex = 0;
    this.addHTMLOutput(timeline);
  });

  test('addAllObjectsMatchingFilterToSelection', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);

    t1.pushSlice(new tracing.trace_model.ThreadSlice('', 'a', 0, 1, {}, 3));
    t1.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'b', 0, 1.1, {}, 2.8));

    var t1asg = t1.asyncSlices;
    t1asg.slices.push(
        tracing.test_utils.newAsyncSliceNamed('a', 0, 1, t1, t1));
    t1asg.slices.push(
        tracing.test_utils.newAsyncSliceNamed('b', 1, 2, t1, t1));

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    var expected = [{slice: t1asg.slices[0].subSlices[0]},
                    {slice: t1.slices[0]}];
    var result = new tracing.Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('a'), result);
    assertEquals(2, result.length);
    assertEquals(expected[0].slice, result[0].slice);
    assertEquals(expected[1].slice, result[1].slice);

    var expected = [{slice: t1asg.slices[1].subSlices[0]},
                    {slice: t1.slices[1]}];
    var result = new tracing.Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('b'), result);
    assertEquals(2, result.length);
    assertEquals(expected[0].slice, result[0].slice);
    assertEquals(expected[1].slice, result[1].slice);
  });

  test('emptyThreadsDeleted', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertEquals(0, timeline.numVisibleTracks);
  });

  test('filteredCounters', function() {
    var model = new tracing.TraceModel();
    var c1 = model.getOrCreateCpu(0);
    c1.getOrCreateCounter('', 'b');
    var p1 = model.getOrCreateProcess(1);
    p1.getOrCreateCounter('', 'a').samples = [1];

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertEquals(2, timeline.numVisibleTracks);

    timeline.categoryFilter = new NoCountersFilter();
    assertEquals(0, timeline.numVisibleTracks);
  });

  test('filteredCpus', function() {
    var model = new tracing.TraceModel();
    var c1 = model.getOrCreateCpu(1);
    c1.getOrCreateCounter('', 'a');

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertEquals(1, timeline.numVisibleTracks);

    timeline.categoryFilter = new NoCpusFilter();
    assertEquals(0, timeline.numVisibleTracks);
  });

  test('filteredProcesses', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    p1.getOrCreateCounter('', 'a');

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertEquals(1, timeline.numVisibleTracks);

    timeline.categoryFilter = new NoProcessesFilter();
    assertEquals(0, timeline.numVisibleTracks);
  });

  test('filteredThreads', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(2);
    t1.pushSlice(tracing.test_utils.newSlice(0, 1));

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertEquals(1, timeline.numVisibleTracks);

    timeline.categoryFilter = new NoThreadsFilter();
    assertEquals(0, timeline.numVisibleTracks);
  });
});
