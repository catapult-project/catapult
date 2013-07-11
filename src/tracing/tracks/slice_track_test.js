// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model.slice');
base.require('tracing.timeline_track_view');
base.require('ui.dom_helpers');

base.unittest.testSuite('tracing.tracks.slice_track', function() {
  var Selection = tracing.Selection;
  var SliceTrack = tracing.tracks.SliceTrack;
  var Slice = tracing.trace_model.Slice;
  var Viewport = tracing.TimelineViewport;

  test('instantiate', function() {
    var div = document.createElement('div');
    this.addHTMLOutput(div);

    var viewport = new Viewport(div);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    div.appendChild(drawingContainer);

    var track = SliceTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.invalidate();

    track.heading = 'testBasicSlices';
    track.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 2.1, {}, 4.8),
      new Slice('', 'b', 1, 7, {}, 0.5),
      new Slice('', 'c', 2, 7.6, {}, 0.4)
    ];
    track.viewport.xSetWorldBounds(0, 8.8, track.clientWidth);
  });

  test('instantiate_shrinkingSliceSize', function() {
    var div = document.createElement('div');
    this.addHTMLOutput(div);

    var viewport = new Viewport(div);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    div.appendChild(drawingContainer);

    var track = SliceTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.invalidate();

    track.heading = 'testShrinkingSliceSizes';
    var x = 0;
    var widths = [10, 5, 4, 3, 2, 1, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05];
    var slices = [];
    for (var i = 0; i < widths.length; i++) {
      var s = new Slice('', 'a', 1, x, {}, widths[i]);
      x += s.duration + 0.5;
      slices.push(s);
    }
    track.slices = slices;
    track.viewport.xSetWorldBounds(0, 1.1 * x, track.clientWidth);
  });

  test('instantiate_elide', function() {
    var optDicts = [{ trackName: 'elideOff', elide: false },
                    { trackName: 'elideOn', elide: true }];

    var tooLongTitle = 'Unless eliding this SHOULD NOT BE DISPLAYED.  ';
    var bigTitle = 'Very big title name that goes on longer ' +
                   'than you may expect';

    for (var dictIndex in optDicts) {
      var dict = optDicts[dictIndex];

      var div = document.createElement('div');
      div.appendChild(document.createTextNode(dict.trackName));
      this.addHTMLOutput(div);

      var viewport = new Viewport(div);
      var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
      div.appendChild(drawingContainer);

      var track = new SliceTrack(viewport);
      drawingContainer.appendChild(track);
      drawingContainer.invalidate();

      track.SHOULD_ELIDE_TEXT = dict.elide;
      track.heading = 'Visual: ' + dict.trackName;
      track.slices = [
        // title, colorId, start, args, opt_duration
        new Slice('', 'a ' + tooLongTitle + bigTitle, 0, 1, {}, 1),
        new Slice('', bigTitle, 1, 2.1, {}, 4.8),
        new Slice('', 'cccc cccc cccc', 1, 7, {}, 0.5),
        new Slice('', 'd', 2, 7.6, {}, 1.0)
      ];
      track.viewport.xSetWorldBounds(0, 9.5, track.clientWidth);
    }
  });

  test('findAllObjectsMatchingInSliceTrack', function() {
    var track = SliceTrack(new tracing.TimelineViewport());
    track.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 2.1, {}, 4.8),
      new Slice('', 'b', 1, 7, {}, 0.5),
      new Slice('', 'c', 2, 7.6, {}, 0.4)
    ];
    var selection = new Selection();
    track.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('b'), selection);

    assertEquals(2, selection.length);
    assertEquals(track.slices[1], selection[0].slice);
    assertEquals(track.slices[2], selection[1].slice);
  });

  test('selectionHitTesting', function() {
    var testEl = document.createElement('div');
    testEl.appendChild(ui.createScopedStyle('heading { width: 100px; }'));
    testEl.style.width = '600px';
    this.addHTMLOutput(testEl);

    var viewport = new Viewport(testEl);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    testEl.appendChild(drawingContainer);

    var track = new SliceTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.updateCanvasSizeIfNeeded_();

    track.heading = 'testSelectionHitTesting';
    track.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 5, {}, 4.8)
    ];
    var y = track.getBoundingClientRect().top + 5;
    var pixelRatio = window.devicePixelRatio || 1;
    var wW = 10;
    var vW = drawingContainer.canvas.getBoundingClientRect().width;
    track.viewport.xSetWorldBounds(0, wW, vW * pixelRatio);

    var selection = new Selection();
    var x = (1.5 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(track.slices[0], selection[0].slice);

    var selection = new Selection();
    x = (2.1 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(0, selection.length);

    var selection = new Selection();
    x = (6.8 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(track.slices[1], selection[0].slice);

    var selection = new Selection();
    x = (9.9 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(0, selection.length);
  });

  test('elide', function() {
    var testEl = document.createElement('div');
    this.addHTMLOutput(testEl);

    var viewport = new Viewport(testEl);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    testEl.appendChild(drawingContainer);

    var track = new SliceTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.updateCanvasSizeIfNeeded_();

    var bigtitle = 'Super duper long long title ' +
        'holy moly when did you get so verbose?';
    var smalltitle = 'small';
    track.heading = 'testElide';
    track.slices = [
      // title, colorId, start, args, opt_duration
      new Slice('', bigtitle, 0, 1, {}, 1),
      new Slice('', smalltitle, 1, 2, {}, 1)
    ];
    track.viewport.xSetWorldBounds(0, 3.3, track.clientWidth);

    var stringWidthPair = undefined;
    var pixWidth = track.viewport.xViewVectorToWorld(1);

    // Small titles on big slices are not elided.
    stringWidthPair = track.elidedTitleCache.get(track, pixWidth, smalltitle,
        track.labelWidth(smalltitle), 1);
    assertEquals(smalltitle, stringWidthPair.string);

    // Keep shrinking the slice until eliding starts.
    var elidedWhenSmallEnough = false;
    for (var sliceLength = 1; sliceLength >= 0.00001; sliceLength /= 2.0) {
      stringWidthPair = track.elidedTitleCache.get(track, pixWidth, smalltitle,
          track.labelWidth(smalltitle), sliceLength);
      if (stringWidthPair.string.length < smalltitle.length) {
        elidedWhenSmallEnough = true;
        break;
      }
    }
    assertTrue(elidedWhenSmallEnough);

    // Big titles are elided immediately.
    var superBigTitle = '';
    for (var x = 0; x < 10; x++) {
      superBigTitle += bigtitle;
    }
    stringWidthPair = track.elidedTitleCache.get(track, pixWidth,
        superBigTitle, track.labelWidth(superBigTitle), 1);
    assertTrue(stringWidthPair.string.length < superBigTitle.length);

    // And elided text ends with ...
    var len = stringWidthPair.string.length;
    assertEquals('...', stringWidthPair.string.substring(len - 3, len));
  });

  test('sliceTrackAddItemNearToProvidedHit', function() {
    var track = new SliceTrack(new tracing.TimelineViewport());
    track.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 2.1, {}, 4.8),
      new Slice('', 'b', 1, 7, {}, 0.5),
      new Slice('', 'c', 2, 7.6, {}, 0.4)
    ];
    var sel = new Selection();
    track.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('b'), sel);
    var ret;

    // Select to the right of B.
    var selRight = new Selection();
    ret = track.addItemNearToProvidedHitToSelection(sel[0], 1, selRight);
    assertTrue(ret);
    assertEquals(track.slices[2], selRight[0].slice);

    // Select to the right of the 2nd b.
    var selRight2 = new Selection();
    ret = track.addItemNearToProvidedHitToSelection(sel[0], 2, selRight2);
    assertTrue(ret);
    assertEquals(track.slices[3], selRight2[0].slice);

    // Select to 2 to the right of the 2nd b.
    var selRightOfRight = new Selection();
    ret = track.addItemNearToProvidedHitToSelection(
        selRight[0], 1, selRightOfRight);
    assertTrue(ret);
    assertEquals(track.slices[3], selRightOfRight[0].slice);

    // Select to the right of the rightmost slice.
    var selNone = new Selection();
    ret = track.addItemNearToProvidedHitToSelection(
        selRightOfRight[0], 1, selNone);
    assertFalse(ret);
    assertEquals(0, selNone.length);

    // Select A and then select left.
    var sel = new Selection();
    track.addAllObjectsMatchingFilterToSelection(
        new tracing.TitleFilter('a'), sel);
    var ret;

    selNone = new Selection();
    ret = track.addItemNearToProvidedHitToSelection(sel[0], -1, selNone);
    assertFalse(ret);
    assertEquals(0, selNone.length);
  });
});
