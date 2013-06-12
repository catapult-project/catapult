// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.timeline_view');
base.require('tracing.trace_model');

'use strict';

base.unittest.testSuite('tracing.timeline_view', function() {
  var newSliceNamed = tracing.test_utils.newSliceNamed;

  var createFullyPopulatedModel = function(opt_withError, opt_withMetadata) {
    var withError = opt_withError !== undefined ? opt_withError : true;
    var withMetadata = opt_withMetadata !== undefined ?
        opt_withMetadata : true;

    var num_tests = 50;
    var testIndex = 0;
    var startTime = 0;

    var model = new tracing.TraceModel();
    for (testIndex = 0; testIndex < num_tests; ++testIndex) {
      var process = model.getOrCreateProcess(10000 + testIndex);
      if (testIndex % 2 == 0) {
        var thread = process.getOrCreateThread('Thread Name Here');
        thread.slices.push(new tracing.trace_model.Slice(
            'foo', 'a', 0, startTime, {}, 1));
        thread.slices.push(new tracing.trace_model.Slice(
            'bar', 'b', 0, startTime + 23, {}, 10));
      } else {
        var thread = process.getOrCreateThread('Name');
        thread.slices.push(new tracing.trace_model.Slice(
            'foo', 'a', 0, startTime + 4, {}, 11));
        thread.slices.push(new tracing.trace_model.Slice(
            'bar', 'b', 0, startTime + 22, {}, 14));
      }
    }
    var p1000 = model.getOrCreateProcess(1000);
    var objects = p1000.objects;
    objects.idWasCreated('0x1000', 'cc', 'LayerTreeHostImpl', 10);
    objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 10,
                        'snapshot-1');
    objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 25,
                        'snapshot-2');
    objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 40,
                        'snapshot-3');
    objects.idWasDeleted('0x1000', 'cc', 'LayerTreeHostImpl', 45);
    model.updateCategories_();

    // Add a known problematic piece of data to test the import errors UI.
    model.importErrors.push('Synthetic Import Error');
    model.updateBounds();

    // Add data with metadata information stored
    model.metadata.push({name: 'a', value: 'testA'});
    model.metadata.push({name: 'b', value: 'testB'});
    model.metadata.push({name: 'c', value: 'testC'});

    return model;
  };

  var visibleTracks = function(trackButtons) {
    return trackButtons.reduce(function(numVisible, button) {
      var style = button.parentElement.style;
      var visible = (style.display.indexOf('none') === -1);
      return visible ? numVisible + 1 : numVisible;
    }, 0);
  };

  var toggleRegExpSelectors = function(regexpSelectors) {
    for (var i = 0; i < regexpSelectors.length; i++) {
      var selector = regexpSelectors[i];
      if (selector.regexp.source !== ui.RegExpSelector.defaultSource)
        selector.isOn = !selector.isOn;
    }
  };

  var modelsEquivalent = function(lhs, rhs) {
    if (lhs.length !== rhs.length)
      return false;
    return lhs.every(function(lhsItem, index) {
      var rhsItem = rhs[index];
      return rhsItem.regexpText === lhsItem.regexpText &&
          rhsItem.isOn === lhsItem.isOn;
    });
  };

  var buildView = function() {
    var view = new tracing.TimelineView();
    view.model = createFullyPopulatedModel();

    var selection = new tracing.Selection();
    view.timeline.addAllObjectsMatchingFilterToSelection({
      matchSlice: function() { return true; }
    }, selection);
    view.timeline.selection = selection;

    return view;
  };

  test('changeModelToSomethingDifferent', function() {
    var model00 = createFullyPopulatedModel(false, false);
    var model11 = createFullyPopulatedModel(true, true);

    var view = new tracing.TimelineView();
    view.style.height = '400px';
    view.model = model00;
    view.model = undefined;
    view.model = model11;
    view.model = model00;
  });

  test('setModelToSameThingAgain', function() {
    var model = createFullyPopulatedModel(false, false);

    // Create a view with am model.
    var view = new tracing.TimelineView();
    view.style.height = '400px';
    view.model = model;

    // Mutate the model and update the view.
    var t123 = model.getOrCreateProcess(123).getOrCreateThread(123);
    t123.pushSlice(newSliceNamed('somethingUnusual', 0, 5));
    view.model = model;

    // Verify that the new bits of the model show up in the view.
    var selection = new tracing.Selection();
    var filter = new tracing.TitleFilter('somethingUnusual');
    view.timeline.addAllObjectsMatchingFilterToSelection(filter, selection);
    assertEquals(selection.length, 1);
  });

  test('trackSelector', function() {
    var timeline = buildView();
    this.addHTMLOutput(timeline);

    var trackSelectorButton = timeline.querySelector('.track-selector-button');
    trackSelectorButton.click();

    var showHiddenTracks = timeline.querySelector('.show-hidden-tracks-button');

    // To start no tracks are disabled, so we can't Show Hidden Tracks
    assertEquals('', showHiddenTracks.getAttribute('disabled'));

    var trackButtonsDOM = timeline.querySelectorAll('.track-button');
    var trackButtons = [];
    for (var i = 0; i < trackButtonsDOM.length; i++)
      trackButtons.push(trackButtonsDOM[i]);

    var lastTrackButton = trackButtons[trackButtons.length - 1];
    lastTrackButton.scrollIntoViewIfNeeded();
    lastTrackButton.click();

    // The track is hidden
    var styleDisplay = lastTrackButton.parentElement.style.display;
    assertNotEquals(-1, styleDisplay.indexOf('none'));

    // A hidden track can now be re-shown.
    assertNull(showHiddenTracks.getAttribute('disabled'));
    showHiddenTracks.click();

    // The track is no longer hidden
    styleDisplay = lastTrackButton.parentElement.style.display;
    assertEquals(-1, styleDisplay.indexOf('none'));

    // No hidden tracks to Show
    assertEquals('', showHiddenTracks.getAttribute('disabled'));

    var trackSelector = timeline.querySelector('.track-selector');
    // initially we have 50 tracks
    assertEquals(50, visibleTracks(trackButtons));

    trackSelector.trackSelectorModel = [
      {regexp: 'Thread', isOn: true},
      {regexp: 'Name\\s\\|', isOn: false}
    ];
    // 25 Tracks have "Name\s\|'
    assertEquals(25, visibleTracks(trackButtons));

    var regexpSelectors =
        trackSelector.querySelectorAll('.regexp-selector');
    toggleRegExpSelectors(regexpSelectors);

    // 25 Tracks have 'Name:'
    assertEquals(25, visibleTracks(trackButtons));

    toggleRegExpSelectors(regexpSelectors);
    // 25 Tracks have "Thread'
    assertEquals(25, visibleTracks(trackButtons));

    showHiddenTracks.click();
    assertEquals(50, visibleTracks(trackButtons));

    var blanks = 0;
    for (var i = 0; i < regexpSelectors.length; i++) {
      var blankRegExp = ui.RegExpSelector.defaultSource;
      if (regexpSelectors[i].regexp.source === blankRegExp) {
        blanks++;
      }
    }
    assertEquals(blanks, 1);
    trackSelectorButton.click();

    var settings = new base.Settings();
    var trackSelectorModelJSON = settings.get('TrackSelector');
    var actual = JSON.parse(trackSelectorModelJSON);
    var expected = [
      {'regexpText': 'Thread', 'isOn': false},
      {'regexpText': 'Name\\s\\|', 'isOn': false},
      {'regexpText': '(?:)', 'isOn': false}
    ];
    // We've stored what we set in the test above.
    assertTrue(modelsEquivalent(actual, expected));

    expected.shift();

    settings.set('TrackSelector', JSON.stringify(expected));
    var aTrackSelector = new tracing.tracks.TrackSelector();
    actual = aTrackSelector.trackSelectorModel;
    // we recovered what we stored
    assertTrue(modelsEquivalent(actual, expected));

    settings.set('TrackSelector', 'junk');
    aTrackSelector = new tracing.tracks.TrackSelector();
    actual = aTrackSelector.trackSelectorModel;
    // we fallback to default
    expected = tracing.tracks.TrackSelector.defaultModel;
    assertTrue(modelsEquivalent(actual, expected));
  });
});
