// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.selection');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tracing.trace_model.slice');
tvcm.require('tracing.tracks.slice_track');

tvcm.unittest.testSuite('tracing.tracks.slice_track_test', function() {
  var Selection = tracing.Selection;
  var SliceTrack = tracing.tracks.SliceTrack;
  var Slice = tracing.trace_model.Slice;

  test('addRectToSelectionTesting', function() {
    var track = new SliceTrack(new tracing.TimelineViewport());
    var slice = new Slice('', 'a', 0, 1, {}, 1);
    track.slices = [slice];
    var sel = new Selection();
    track.addRectToSelection(track.slices[0], sel);
    assertEquals(1, sel.length);
    assertEquals(slice, sel[0]);
  });
});
