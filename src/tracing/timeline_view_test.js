// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_view');
base.require('tracing.trace_model');

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
        thread.sliceGroup.pushSlice(new tracing.trace_model.Slice(
            'foo', 'a', 0, startTime, {}, 1));
        thread.sliceGroup.pushSlice(new tracing.trace_model.Slice(
            'bar', 'b', 0, startTime + 23, {}, 10));
      } else {
        var thread = process.getOrCreateThread('Name');
        thread.sliceGroup.pushSlice(new tracing.trace_model.Slice(
            'foo', 'a', 0, startTime + 4, {}, 11));
        thread.sliceGroup.pushSlice(new tracing.trace_model.Slice(
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
    t123.sliceGroup.pushSlice(newSliceNamed('somethingUnusual', 0, 5));
    view.model = model;

    // Verify that the new bits of the model show up in the view.
    var selection = new tracing.Selection();
    var filter = new tracing.TitleFilter('somethingUnusual');
    view.timeline.addAllObjectsMatchingFilterToSelection(filter, selection);
    assertEquals(selection.length, 1);
  });

});
