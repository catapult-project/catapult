// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.trace_model.slice_group');

base.unittest.testSuite('tracing.tracks.slice_group_track', function() {
  var SliceGroup = tracing.trace_model.SliceGroup;
  var SliceGroupTrack = tracing.tracks.SliceGroupTrack;
  var newSliceNamed = tracing.test_utils.newSliceNamed;

  test('subRowBuilderBasic', function() {
    var group = new SliceGroup();
    var sA = group.pushSlice(newSliceNamed('a', 1, 2));
    var sB = group.pushSlice(newSliceNamed('a', 3, 1));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(1, subRows.length);
    assertEquals(2, subRows[0].length);
    assertArrayEquals([sA, sB], subRows[0]);
  });

  test('subRowBuilderBasic2', function() {
    var group = new SliceGroup();
    var sA = group.pushSlice(newSliceNamed('a', 1, 4));
    var sB = group.pushSlice(newSliceNamed('b', 3, 1));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertEquals(1, subRows[0].length);
    assertEquals(1, subRows[1].length);
    assertArrayEquals([sA], subRows[0]);
    assertArrayEquals([sB], subRows[1]);
  });

  test('subRowBuilderNestedExactly', function() {
    var group = new SliceGroup();
    var sA = group.pushSlice(newSliceNamed('a', 1, 4));
    var sB = group.pushSlice(newSliceNamed('b', 1, 4));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertEquals(1, subRows[0].length);
    assertEquals(1, subRows[1].length);
    assertArrayEquals([sB], subRows[0]);
    assertArrayEquals([sA], subRows[1]);
  });

  test('subRowBuilderInstantEvents', function() {
    var group = new SliceGroup();
    var sA = group.pushSlice(newSliceNamed('a', 1, 0));
    var sB = group.pushSlice(newSliceNamed('b', 2, 0));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(1, subRows.length);
    assertEquals(2, subRows[0].length);
    assertArrayEquals([sA, sB], subRows[0]);
  });

  test('subRowBuilderTwoInstantEvents', function() {
    var group = new SliceGroup();
    var sB = group.pushSlice(newSliceNamed('b', 1, 0));
    var sA = group.pushSlice(newSliceNamed('a', 1, 0));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertArrayEquals([sA], subRows[0]);
    assertArrayEquals([sB], subRows[1]);
  });

  test('subRowBuilderOutOfOrderAddition', function() {
    var group = new SliceGroup();

    // Pattern being tested:
    // [    a     ][   b   ]
    // Where insertion is done backward.
    var sB = group.pushSlice(newSliceNamed('b', 3, 1));
    var sA = group.pushSlice(newSliceNamed('a', 1, 2));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(1, subRows.length);
    assertEquals(2, subRows[0].length);
    assertArrayEquals([sA, sB], subRows[0]);
  });

  test('subRowBuilderOutOfOrderAddition2', function() {
    var group = new SliceGroup();

    // Pattern being tested:
    // [    a     ]
    //   [  b   ]
    // Where insertion is done backward.
    var sB = group.pushSlice(newSliceNamed('b', 3, 1));
    var sA = group.pushSlice(newSliceNamed('a', 1, 5));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertEquals(1, subRows[0].length);
    assertEquals(1, subRows[1].length);
    assertArrayEquals([sA], subRows[0]);
    assertArrayEquals([sB], subRows[1]);
  });

  test('subRowBuilderOnNestedZeroLength', function() {
    var group = new SliceGroup();

    // Pattern being tested:
    // [    a    ]
    // [  b1 ]  []<- b2 where b2.duration = 0 and b2.end == a.end.
    var sB1 = group.pushSlice(newSliceNamed('b1', 1, 2));
    var sB2 = group.pushSlice(newSliceNamed('b2', 4, 0));
    var sA = group.pushSlice(newSliceNamed('a', 1, 3));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertArrayEquals([sA], subRows[0]);
    assertArrayEquals([sB1, sB2], subRows[1]);
  });

  test('subRowBuilderOnGroup1', function() {
    var group = new SliceGroup();

    // Pattern being tested:
    // [    a     ]   [  c   ]
    //   [  b   ]
    var sA = group.pushSlice(newSliceNamed('a', 1, 3));
    var sB = group.pushSlice(newSliceNamed('b', 1.5, 1));
    var sC = group.pushSlice(newSliceNamed('c', 5, 0));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;
    var subRows = track.subRows;

    assertEquals(0, track.badSlices_.length);
    assertEquals(2, subRows.length);
    assertArrayEquals([sA, sC], subRows[0]);
    assertArrayEquals([sB], subRows[1]);
  });

  test('subRowBuilderOnGroup2', function() {
    var group = new SliceGroup();

    // Pattern being tested:
    // [    a     ]   [  d   ]
    //   [  b   ]
    //    [ c ]
    var sA = group.pushSlice(newSliceNamed('a', 1, 3));
    var sB = group.pushSlice(newSliceNamed('b', 1.5, 1));
    var sC = group.pushSlice(newSliceNamed('c', 1.75, 0.5));
    var sD = group.pushSlice(newSliceNamed('c', 5, 0.25));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;

    var subRows = track.subRows;
    assertEquals(0, track.badSlices_.length);
    assertEquals(3, subRows.length);
    assertArrayEquals([sA, sD], subRows[0]);
    assertArrayEquals([sB], subRows[1]);
    assertArrayEquals([sC], subRows[2]);
  });

  test('trackFiltering', function() {
    var group = new SliceGroup();

    var sA = group.pushSlice(newSliceNamed('a', 1, 3));
    var sB = group.pushSlice(newSliceNamed('b', 1.5, 1));

    var track = new SliceGroupTrack(new tracing.TimelineViewport());
    track.group = group;

    assertEquals(2, track.subRows.length);
    assertTrue(track.hasVisibleContent);

    track.categoryFilter = new tracing.TitleFilter('x');
    assertFalse(track.hasVisibleContent);

    track.categoryFilter = new tracing.TitleFilter('a');
    assertTrue(track.hasVisibleContent);
    assertEquals(1, track.subRows.length);

    track.categoryFilter = new tracing.TitleFilter('b');
    assertTrue(track.hasVisibleContent);
    assertEquals(1, track.subRows.length);
  });
});
