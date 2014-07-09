// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.selection');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tracing.trace_model.sample');
tvcm.require('tracing.trace_model.stack_frame');
tvcm.require('tracing.tracks.sample_track');

tvcm.unittest.testSuite('tracing.tracks.sample_track_test', function() {
  var Selection = tracing.Selection;
  var SampleTrack = tracing.tracks.SampleTrack;
  var Sample = tracing.trace_model.Sample;
  var StackFrame = tracing.trace_model.StackFrame;

  test('addRectToSelectionTesting', function() {
    var track = new SampleTrack(new tracing.TimelineViewport());
    var fA = new StackFrame(undefined, 1, 'cat', 'a', 7);
    var sample = new Sample(undefined, undefined, 'instructions_retired',
                            10, fA, 10);
    track.samples = [sample];
    var sel = new Selection();
    track.addRectToSelection(track.samples[0], sel);
    assertEquals(1, sel.length);
    assertEquals(sample, sel[0]);
  });
});
