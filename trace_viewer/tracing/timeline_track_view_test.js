// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tracing.importer.trace_event_importer');

tvcm.unittest.testSuite('tracing.timeline_track_view_test', function() {

  var Selection = tracing.Selection;
  var SelectionState = tracing.trace_model.SelectionState;

  function contains(array, element) {
    for (var i = 0; i < array.length; i++) {
      if (array[i] === element) {
        return true;
      }
    }
    return false;
  };

  function checkSelectionStates(timeline, selection, highlight) {
    selection = selection || [];
    highlight = highlight || [];

    assertEquals(selection.length, timeline.selection.length);
    assertEquals(highlight.length, timeline.highlight.length);

    assertArrayEquals(selection, timeline.selection);
    assertArrayEquals(highlight, timeline.highlight);

    timeline.model.iterateAllEvents(function(event) {
      if (contains(selection, event))
        assertEquals(SelectionState.SELECTED, event.selectionState);
      else if (contains(highlight, event))
        assertEquals(SelectionState.HIGHLIGHTED, event.selectionState);
      else if (highlight.length)
        assertEquals(SelectionState.DIMMED, event.selectionState);
      else
        assertEquals(SelectionState.NONE, event.selectionState);
    });
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

    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'a', 0, 1, {}, 3));
    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'b', 0, 1.1, {}, 2.8));

    var t1asg = t1.asyncSliceGroup;
    t1asg.slices.push(
        tracing.test_utils.newAsyncSliceNamed('a', 0, 1, t1, t1));
    t1asg.slices.push(
        tracing.test_utils.newAsyncSliceNamed('b', 1, 2, t1, t1));

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    var expected = [t1asg.slices[0].subSlices[0],
                    t1.sliceGroup.slices[0]];
    var result = new tracing.Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('a'), result);
    assertEquals(2, result.length);
    assertEquals(expected[0], result[0]);
    assertEquals(expected[1], result[1]);

    var expected = [t1asg.slices[1].subSlices[0],
                    t1.sliceGroup.slices[1]];
    var result = new tracing.Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('b'), result);
    assertEquals(2, result.length);
    assertEquals(expected[0], result[0]);
    assertEquals(expected[1], result[1]);
  });

  test('emptyThreadsDeleted', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertFalse(timeline.hasVisibleContent);
  });

  test('filteredCounters', function() {
    var model = new tracing.TraceModel();
    var c1 = model.kernel.getOrCreateCpu(0);
    c1.getOrCreateCounter('', 'b');

    var p1 = model.getOrCreateProcess(1);
    var ctr = p1.getOrCreateCounter('', 'a');
    var series = new tracing.trace_model.CounterSeries('a', 0);
    series.addCounterSample(0, 1);
    ctr.addSeries(series);

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertTrue(timeline.hasVisibleContent);
  });

  test('filteredCpus', function() {
    var model = new tracing.TraceModel();
    var c1 = model.kernel.getOrCreateCpu(1);
    c1.getOrCreateCounter('', 'a');

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertTrue(timeline.hasVisibleContent);
  });

  test('filteredProcesses', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    p1.getOrCreateCounter('', 'a');

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertTrue(timeline.hasVisibleContent);
  });

  test('filteredThreads', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(2);
    t1.sliceGroup.pushSlice(tracing.test_utils.newSlice(0, 1));

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    assertTrue(timeline.hasVisibleContent);
  });

  test('selectionAndHighlight', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'ab', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'B'}
    ];
    var model = new tracing.TraceModel(events);
    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    var selection = new Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('a'), selection);

    var highlight = new Selection();
    timeline.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('b'), highlight);

    // Test for faulty input.
    assertThrows(function() {
      timeline.selection = 'selection';
    });

    assertThrows(function() {
      timeline.highlight = 1;
    });

    assertThrows(function() {
      timeline.setSelectionAndHighlight(0, false);
    });

    // Check state after reset.
    timeline.setSelectionAndHighlight(null, null);
    checkSelectionStates(timeline, null, null);

    // Add selection only.
    timeline.selection = selection;
    assertEquals(selection, timeline.selection);
    checkSelectionStates(timeline, selection, null);

    // Reset selection.
    timeline.selection = null;
    assertEquals(0, timeline.selection.length);
    checkSelectionStates(timeline, null, null);

    // Add highlight only.
    timeline.highlight = highlight;
    assertEquals(highlight, timeline.highlight);
    checkSelectionStates(timeline, null, highlight);

    // Reset highlight
    timeline.highlight = null;
    assertEquals(0, timeline.highlight.length);
    checkSelectionStates(timeline, null, null);

    // Add selection and highlight.
    timeline.setSelectionAndHighlight(selection, highlight);
    checkSelectionStates(timeline, selection, highlight);

    // Selection replaces old selection.
    var subSelection = selection.subSelection(0, 1);
    timeline.selection = subSelection;
    checkSelectionStates(timeline, subSelection, highlight);

    // Highlight replaces old highlight.
    var subHighlight = highlight.subSelection(1, 2);
    timeline.highlight = subHighlight;
    checkSelectionStates(timeline, subSelection, subHighlight);

    // Set selection and clear highlight.
    timeline.setSelectionAndClearHighlight(selection);
    checkSelectionStates(timeline, selection, null);

    // Set highlight and clear selection.
    timeline.setHighlightAndClearSelection(highlight);
    checkSelectionStates(timeline, null, highlight);

    // Reset both.
    timeline.setSelectionAndHighlight(null, null);
    checkSelectionStates(timeline, null, null);
  });

  test('interestRange', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'a', args: {}, pid: 52, ts: 634, cat: 'foo', tid: 53, ph: 'E'}
    ];
    var model = new tracing.TraceModel(events);
    var trackView = new tracing.TimelineTrackView();
    trackView.model = model;
    this.addHTMLOutput(trackView);

    var slice = model.processes[52].threads[53].sliceGroup.slices[2];
    trackView.viewport.interestRange.setMinAndMax(slice.start, slice.end);
  });

  test('emptyInterestRange', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'a', args: {}, pid: 52, ts: 634, cat: 'foo', tid: 53, ph: 'E'}
    ];
    var model = new tracing.TraceModel(events);
    var trackView = new tracing.TimelineTrackView();
    trackView.model = model;
    this.addHTMLOutput(trackView);
    trackView.viewport.interestRange.reset();
  });


  test('thinnestInterestRange', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'c', args: {}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'a', args: {}, pid: 52, ts: 634, cat: 'foo', tid: 53, ph: 'E'}
    ];
    var model = new tracing.TraceModel(events);
    var trackView = new tracing.TimelineTrackView();
    trackView.model = model;
    this.addHTMLOutput(trackView);
    trackView.viewport.interestRange.reset();

    var slice = model.processes[52].threads[53].sliceGroup.slices[2];
    trackView.viewport.interestRange.setMinAndMax(slice.start, slice.start);
  });
});
