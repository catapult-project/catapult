// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.analysis_view');
base.require('tracing.test_utils');
base.require('tracing.trace_model');
base.require('tracing.selection');

base.unittest.testSuite('tracing.analysis.analysis_view', function() {
  var TraceModel = tracing.TraceModel;
  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var ObjectInstance = tracing.trace_model.ObjectInstance;
  var DefaultObjectSnapshotView = tracing.analysis.DefaultObjectSnapshotView;
  var DefaultObjectInstanceView = tracing.analysis.DefaultObjectInstanceView;

  function withRegisteredType(registrar, typeName,
                              typeConstructor, opt_options, fn) {
    registrar.register(typeName, typeConstructor, opt_options);
    try {
      fn();
    } finally {
      registrar.unregister(typeName);
    }
  }

  test('instantiate_analysisWithObjects', function() {
    var model = new TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var objects = p1.objects;
    var i10 = objects.idWasCreated('0x1000', 'cc', 'LayerTreeHostImpl', 10);
    var s10 = objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 10,
                                  'snapshot-1');
    var s25 = objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 25,
                                  'snapshot-2');
    var s40 = objects.addSnapshot('0x1000', 'cc', 'LayerTreeHostImpl', 40,
                                  'snapshot-3');
    objects.idWasDeleted('0x1000', 'cc', 'LayerTreeHostImpl', 45);

    var track = {};
    var selection = new Selection();
    selection.addObjectInstance(track, i10);
    selection.addObjectSnapshot(track, s10);
    selection.addObjectSnapshot(track, s25);
    selection.addObjectSnapshot(track, s40);

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('analyzeSelectionWithObjectSnapshotUnknownType', function() {
    var i10 = new ObjectInstance({}, '0x1000', 'cat', 'someUnhandledName', 10);
    var s10 = i10.addSnapshot(10, {foo: 1});

    var selection = new Selection();
    selection.addObjectSnapshot({}, s10);

    var view = new AnalysisView();
    view.selection = selection;
    assertTrue(view.currentView instanceof DefaultObjectSnapshotView);
    assertEquals(s10, view.currentView.objectSnapshot);
  });

  test('analyzeSelectionWithObjectSnapshotKnownType', function() {
    var i10 = new ObjectInstance({}, '0x1000', 'cat', 'MyView', 10);
    var s10 = i10.addSnapshot(10, {foo: 1});

    var selection = new Selection();
    selection.addObjectSnapshot({}, s10);

    var MyView = ui.define(
        'my-view', tracing.analysis.ObjectSnapshotView);
    MyView.prototype = {
      __proto__: tracing.analysis.ObjectSnapshotView.prototype,

      decorate: function() {
      },

      updateContents: function() {
        this.textContent = 'hello';
      }
    };

    var view = new AnalysisView();
    withRegisteredType(
        tracing.analysis.ObjectSnapshotView, 'MyView', MyView, undefined,
        function() {
          view.selection = selection;
          assertTrue(view.currentView instanceof MyView);
          assertEquals(s10, view.currentView.objectSnapshot);
          assertEquals('hello', view.currentView.textContent);
        });
  });

  test('analyzeSelectionWithObjectInstanceUnknownType', function() {
    var i10 = new ObjectInstance({}, '0x1000', 'cat', 'someUnhandledName', 10);

    var selection = new Selection();
    selection.addObjectInstance({}, i10);

    var view = new AnalysisView();
    view.selection = selection;
    assertTrue(view.currentView instanceof DefaultObjectInstanceView);
    assertEquals(i10, view.currentView.objectInstance);
  });

  test('analyzeSelectionWithObjectInstanceKnownType', function() {
    var i10 = new ObjectInstance({}, '0x1000', 'cat', 'MyView', 10);

    var selection = new Selection();
    selection.addObjectInstance({}, i10);

    var MyView = ui.define(
        'my-view', tracing.analysis.ObjectInstanceView);
    MyView.prototype = {
      __proto__: tracing.analysis.ObjectInstanceView.prototype,

      decorate: function() {
      },

      updateContents: function() {
        this.textContent = 'hello';
      }
    };

    var view = new AnalysisView();
    withRegisteredType(
        tracing.analysis.ObjectInstanceView,
        'MyView', MyView, undefined, function() {
          view.selection = selection;
          assertTrue(view.currentView instanceof MyView);
          assertEquals(i10, view.currentView.objectInstance);
          assertEquals('hello', view.currentView.textContent);
        });
  });

  test('analyzeSelectionWithSliceKnownType', function() {
    var s10 = new tracing.trace_model.Slice('cat', 'MySlice', 0, 10, {}, 4);

    var selection = new tracing.Selection();
    selection.addSlice({}, s10);

    var MySlice = ui.define(
        'my-slice', tracing.analysis.SliceView);
    MySlice.prototype = {
      __proto__: tracing.analysis.SliceView.prototype,

      decorate: function() {
      },

      updateContents: function() {
        this.textContent = 'hello';
      }
    };

    var view = new AnalysisView();
    withRegisteredType(
        tracing.analysis.SliceView,
        'MySlice', MySlice, undefined, function() {
          view.selection = selection;
          assertTrue(view.currentView instanceof MySlice);
          assertEquals(s10, view.currentView.slice);
          assertEquals('hello', view.currentView.textContent);
        });
  });
});
