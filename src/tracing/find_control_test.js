// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.find_control');

base.unittest.testSuite('tracing.find_control', function() {
  /*
   * Just enough of the Timeline to support the tests below.
   */
  var FakeTimeline = ui.define('div');

  FakeTimeline.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.addAllObjectsMatchingFilterToSelectionReturnValue = [];

      this.selection = new tracing.Selection();
      this.keyHelp = '<keyHelp>';

      // Put some simple UI in for testing purposes.
      var noteEl = document.createElement('div');
      noteEl.textContent = 'FakeTimeline:';
      this.appendChild(noteEl);

      this.statusEl_ = document.createElement('div');
      this.appendChild(this.statusEl_);
      this.refresh_();
    },

    refresh_: function() {
      var status;
      if (this.model)
        status = 'model=set';
      else
        status = 'model=undefined';
      this.statusEl_.textContent = status;
    },

    zoomToSelection: function() {},

    panToSelection: function() {},

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      var n = this.addAllObjectsMatchingFilterToSelectionReturnValue.length;
      for (var i = 0; i < n; i++)
        selection.push_(
            this.addAllObjectsMatchingFilterToSelectionReturnValue[i]);
    }
  };

  test('instantiate', function() {
    var ctl = new tracing.FindControl();
    var didFindPrevious = false;
    var didFindNext = false;
    ctl.controller = {
      findNext: function() {
        didFindNext = true;
      },

      findPrevious: function() {
        didFindPrevious = true;
      },

      reset: function() {},

      filterHits: [],

      currentHitIndex: 0
    };

    this.addHTMLOutput(ctl);

    ctl.querySelector('input').focus();
    ctl.querySelector('input').blur();

    ctl.querySelector('.find-previous').click();
    assertTrue(didFindPrevious);
    ctl.querySelector('.find-next').click();
    assertTrue(didFindNext);
  });

  test('findControllerNoTimeline', function() {
    var controller = new tracing.FindController();
    controller.findNext();
    controller.findPrevious();
  });

  test('findControllerEmptyHit', function() {
    var timeline = new FakeTimeline();
    var controller = new tracing.FindController();
    controller.timeline = timeline;

    timeline.selection = new tracing.Selection();
    controller.findNext();
    assertArrayShallowEquals([], timeline.selection);
    controller.findPrevious();
    assertArrayShallowEquals([], timeline.selection);
  });

  test('findControllerOneHit', function() {
    var timeline = new FakeTimeline();
    var controller = new tracing.FindController();
    controller.timeline = timeline;

    timeline.addAllObjectsMatchingFilterToSelectionReturnValue = [1];
    controller.filterText = 'asdf';

    controller.findNext();
    assertArrayShallowEquals([1], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([1], timeline.selection);
    controller.findPrevious();
    assertArrayShallowEquals([1], timeline.selection);
  });

  test('findControllerMultipleHits', function() {
    var timeline = new FakeTimeline();
    var controller = new tracing.FindController();
    controller.timeline = timeline;

    timeline.addAllObjectsMatchingFilterToSelectionReturnValue = [1, 2, 3];
    controller.filterText = 'asdf';

    // Loop through hits then when we wrap, try moving backward.
    controller.findNext();
    assertArrayShallowEquals([1], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([2], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([3], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([1], timeline.selection);
    controller.findPrevious();
    assertArrayShallowEquals([3], timeline.selection);
    controller.findPrevious();
    assertArrayShallowEquals([2], timeline.selection);
  });

  test('findControllerChangeFilterAfterNext', function() {
    var timeline = new FakeTimeline();
    var controller = new tracing.FindController();
    controller.timeline = timeline;

    timeline.addAllObjectsMatchingFilterToSelectionReturnValue = [1, 2, 3];
    controller.filterText = 'asdf';

    // Loop through hits then when we wrap, try moving backward.
    controller.findNext();
    timeline.addAllObjectsMatchingFilterToSelectionReturnValue = [4];
    controller.filterText = 'asdfsf';
    controller.findNext();
    assertArrayShallowEquals([4], timeline.selection);
  });

  test('findControllerSelectsAllItemsFirst', function() {
    var timeline = new FakeTimeline();
    var controller = new tracing.FindController();
    controller.timeline = timeline;

    timeline.addAllObjectsMatchingFilterToSelectionReturnValue = [1, 2, 3];
    controller.filterText = 'asdfsf';
    assertArrayShallowEquals([1, 2, 3], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([1], timeline.selection);
    controller.findNext();
    assertArrayShallowEquals([2], timeline.selection);
  });

  test('findControllerWithRealTimeline', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);
    t1.sliceGroup.pushSlice(new tracing.trace_model.ThreadSlice(
        '', 'a', 0, 1, {}, 3));

    var timeline = new tracing.TimelineTrackView();
    timeline.model = model;

    var controller = new tracing.FindController();
    controller.timeline = timeline;

    // Test find with no filterText.
    controller.findNext();

    // Test find with filter txt.
    controller.filterText = 'a';
    controller.findNext();
    assertEquals(1, timeline.selection.length);
    assertEquals(t1.sliceGroup.slices[0], timeline.selection[0].slice);

    controller.filterText = 'xxx';
    controller.findNext();
    assertEquals(0, timeline.selection.length);
    controller.findNext();
    assertEquals(0, timeline.selection.length);
  });
});
