// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model.slice_group');

base.unittest.testSuite('tracing.trace_model.slice_group', function() {
  var Slice = tracing.trace_model.Slice;
  var SliceGroup = tracing.trace_model.SliceGroup;
  var newSlice = tracing.test_utils.newSlice;
  var newSliceNamed = tracing.test_utils.newSliceNamed;

  test('basicBeginEnd', function() {
    var group = new SliceGroup();
    assertEquals(group.openSliceCount, 0);
    var sliceA = group.beginSlice('', 'a', 1, {a: 1});
    assertEquals(1, group.openSliceCount);
    assertEquals('a', sliceA.title);
    assertEquals(1, sliceA.start);
    assertEquals(1, sliceA.args.a);

    var sliceB = group.endSlice(3);
    assertEquals(sliceA, sliceB);
    assertEquals(2, sliceB.duration);
  });

  test('nestedBeginEnd', function() {
    var group = new SliceGroup();
    assertEquals(group.openSliceCount, 0);
    group.beginSlice('', 'a', 1);
    group.beginSlice('', 'b', 2);
    group.endSlice(2.5);
    group.endSlice(3);

    assertEquals(2, group.slices.length);
    assertEquals('b', group.slices[0].title);
    assertEquals(0.5, group.slices[0].duration);

    assertEquals('a', group.slices[1].title);
    assertEquals(2, group.slices[1].duration);
  });

  test('basicMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.endSlice(2);
    b.beginSlice('', 'two', 3);
    b.endSlice(5);

    var m = SliceGroup.merge(a, b);
    assertEquals(2, m.slices.length);

    assertEquals('one', m.slices[0].title);
    assertEquals(1, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('two', m.slices[1].title);
    assertEquals(3, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);
  });

  test('nestedMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.endSlice(4);
    b.beginSlice('', 'two', 2);
    b.endSlice(3);

    var m = SliceGroup.merge(a, b);
    assertEquals(2, m.slices.length);

    assertEquals('two', m.slices[0].title);
    assertEquals(2, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('one', m.slices[1].title);
    assertEquals(1, m.slices[1].start);
    assertEquals(3, m.slices[1].duration);
  });

  test('startSplitMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 2);
    a.endSlice(4);
    b.beginSlice('', 'two', 1);
    b.endSlice(3);

    var m = SliceGroup.merge(a, b);
    assertEquals(3, m.slices.length);

    assertEquals('two', m.slices[0].title);
    assertEquals(1, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('two (cont.)', m.slices[1].title);
    assertEquals(2, m.slices[1].start);
    assertEquals(1, m.slices[1].duration);

    assertEquals('one', m.slices[2].title);
    assertEquals(2, m.slices[2].start);
    assertEquals(2, m.slices[2].duration);
  });

  test('startSplitTwoMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 3);
    a.endSlice(6);
    b.beginSlice('', 'two', 1);
    b.beginSlice('', 'three', 2);
    b.endSlice(4);
    b.endSlice(5);

    var m = SliceGroup.merge(a, b);
    assertEquals(5, m.slices.length);

    assertEquals('three', m.slices[0].title);
    assertEquals(2, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('two', m.slices[1].title);
    assertEquals(1, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);

    assertEquals('three (cont.)', m.slices[2].title);
    assertEquals(3, m.slices[2].start);
    assertEquals(1, m.slices[2].duration);

    assertEquals('two (cont.)', m.slices[3].title);
    assertEquals(3, m.slices[3].start);
    assertEquals(2, m.slices[3].duration);

    assertEquals('one', m.slices[4].title);
    assertEquals(3, m.slices[4].start);
    assertEquals(3, m.slices[4].duration);
  });

  test('startSplitTwiceMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 2);
    a.beginSlice('', 'two', 3);
    a.endSlice(5);
    a.endSlice(6);
    b.beginSlice('', 'three', 1);
    b.endSlice(4);

    var m = SliceGroup.merge(a, b);
    assertEquals(5, m.slices.length);

    assertEquals('three', m.slices[0].title);
    assertEquals(1, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('three (cont.)', m.slices[1].title);
    assertEquals(2, m.slices[1].start);
    assertEquals(1, m.slices[1].duration);

    assertEquals('three (cont.)', m.slices[2].title);
    assertEquals(3, m.slices[2].start);
    assertEquals(1, m.slices[2].duration);

    assertEquals('two', m.slices[3].title);
    assertEquals(3, m.slices[3].start);
    assertEquals(2, m.slices[3].duration);

    assertEquals('one', m.slices[4].title);
    assertEquals(2, m.slices[4].start);
    assertEquals(4, m.slices[4].duration);
  });

  test('endSplitMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.endSlice(3);
    b.beginSlice('', 'two', 2);
    b.endSlice(4);

    var m = SliceGroup.merge(a, b);
    assertEquals(3, m.slices.length);

    assertEquals('two', m.slices[0].title);
    assertEquals(2, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('one', m.slices[1].title);
    assertEquals(1, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);

    assertEquals('two (cont.)', m.slices[2].title);
    assertEquals(3, m.slices[2].start);
    assertEquals(1, m.slices[2].duration);
  });

  test('endSplitTwoMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.endSlice(4);
    b.beginSlice('', 'two', 2);
    b.beginSlice('', 'three', 3);
    b.endSlice(5);
    b.endSlice(6);

    var m = SliceGroup.merge(a, b);
    assertEquals(5, m.slices.length);

    assertEquals('three', m.slices[0].title);
    assertEquals(3, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('two', m.slices[1].title);
    assertEquals(2, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);

    assertEquals('one', m.slices[2].title);
    assertEquals(1, m.slices[2].start);
    assertEquals(3, m.slices[2].duration);

    assertEquals('three (cont.)', m.slices[3].title);
    assertEquals(4, m.slices[3].start);
    assertEquals(1, m.slices[3].duration);

    assertEquals('two (cont.)', m.slices[4].title);
    assertEquals(4, m.slices[4].start);
    assertEquals(2, m.slices[4].duration);
  });

  test('endSplitTwiceMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.beginSlice('', 'two', 2);
    a.endSlice(4);
    a.endSlice(5);
    b.beginSlice('', 'three', 3);
    b.endSlice(6);

    var m = SliceGroup.merge(a, b);
    assertEquals(5, m.slices.length);

    assertEquals('three', m.slices[0].title);
    assertEquals(3, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('two', m.slices[1].title);
    assertEquals(2, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);

    assertEquals('three (cont.)', m.slices[2].title);
    assertEquals(4, m.slices[2].start);
    assertEquals(1, m.slices[2].duration);

    assertEquals('one', m.slices[3].title);
    assertEquals(1, m.slices[3].start);
    assertEquals(4, m.slices[3].duration);

    assertEquals('three (cont.)', m.slices[4].title);
    assertEquals(5, m.slices[4].start);
    assertEquals(1, m.slices[4].duration);
  });

  // Input:
  // A:  |    one     |       |     two     |
  //
  // B:       |         three         |
  //
  // Output:
  //     |    one     | three |     two     |
  //          | three |       | three |
  test('splitTwiceMerge', function() {
    var a = new SliceGroup();
    var b = new SliceGroup();
    a.beginSlice('', 'one', 1);
    a.endSlice(3);
    a.beginSlice('', 'two', 4);
    a.endSlice(6);
    b.beginSlice('', 'three', 2);
    b.endSlice(5);

    var m = SliceGroup.merge(a, b);
    assertEquals(5, m.slices.length);

    assertEquals('three', m.slices[0].title);
    assertEquals(2, m.slices[0].start);
    assertEquals(1, m.slices[0].duration);

    assertEquals('one', m.slices[1].title);
    assertEquals(1, m.slices[1].start);
    assertEquals(2, m.slices[1].duration);

    assertEquals('three (cont.)', m.slices[2].title);
    assertEquals(3, m.slices[2].start);
    assertEquals(1, m.slices[2].duration);

    assertEquals('three (cont.)', m.slices[3].title);
    assertEquals(4, m.slices[3].start);
    assertEquals(1, m.slices[3].duration);

    assertEquals('two', m.slices[4].title);
    assertEquals(4, m.slices[4].start);
    assertEquals(2, m.slices[4].duration);
  });

  test('bounds', function() {
    var group = new SliceGroup();
    group.updateBounds();
    assertEquals(group.bounds.min, undefined);
    assertEquals(group.bounds.max, undefined);

    group.pushSlice(newSlice(1, 3));
    group.pushSlice(newSlice(7, 2));
    group.updateBounds();
    assertEquals(1, group.bounds.min);
    assertEquals(9, group.bounds.max);
  });

  test('boundsWithPartial', function() {
    var group = new SliceGroup();
    group.beginSlice('', 'a', 7);
    group.updateBounds();
    assertEquals(7, group.bounds.min);
    assertEquals(7, group.bounds.max);
  });

  test('boundsWithTwoPartials', function() {
    var group = new SliceGroup();
    group.beginSlice('', 'a', 0);
    group.beginSlice('', 'a', 1);
    group.updateBounds();
    assertEquals(0, group.bounds.min);
    assertEquals(1, group.bounds.max);
  });

  test('boundsWithBothPartialAndRegular', function() {
    var group = new SliceGroup();
    group.updateBounds();
    assertEquals(undefined, group.bounds.min);
    assertEquals(undefined, group.bounds.max);

    group.pushSlice(newSlice(1, 3));
    group.beginSlice('', 'a', 7);
    group.updateBounds();
    assertEquals(1, group.bounds.min);
    assertEquals(7, group.bounds.max);
  });

  test('autocloserBasic', function() {
    var group = new SliceGroup();
    assertEquals(group.openSliceCount, 0);

    group.pushSlice(newSliceNamed('a', 1, 0.5));

    group.beginSlice('', 'b', 2);
    group.beginSlice('', 'c', 2.5);
    group.endSlice(3);

    group.autoCloseOpenSlices();
    group.updateBounds();

    assertEquals(1, group.bounds.min);
    assertEquals(3, group.bounds.max);
    assertEquals(3, group.slices.length);
    assertEquals('a', group.slices[0].title);
    assertEquals('c', group.slices[1].title);
    assertEquals('b', group.slices[2].title);
    assertTrue(group.slices[2].didNotFinish);
    assertEquals(1, group.slices[2].duration);
  });

  test('autocloserWithSubTasks', function() {
    var group = new SliceGroup();
    assertEquals(group.openSliceCount, 0);

    group.beginSlice('', 'a', 1);
    group.beginSlice('', 'b1', 2);
    group.endSlice(3);
    group.beginSlice('', 'b2', 3);

    group.autoCloseOpenSlices();
    assertEquals(3, group.slices.length);
    assertEquals('b1', group.slices[0].title);

    assertEquals('b2', group.slices[1].title);
    assertTrue(group.slices[1].didNotFinish);
    assertEquals(0, group.slices[1].duration);

    assertEquals('a', group.slices[2].title);
    assertTrue(group.slices[2].didNotFinish);
    assertEquals(2, group.slices[2].duration);
  });

  // TODO: test cretion of subSlices
});
