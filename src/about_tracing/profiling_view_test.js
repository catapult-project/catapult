// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.events');
base.require('about_tracing.profiling_view');
base.require('about_tracing.tracing_controller');
base.require('ui.dom_helpers');

base.unittest.testSuite('about_tracing.profiling_view', function() {
  var testDataString = JSON.stringify([
    {name: 'a', args: {}, pid: 52, ts: 15000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'a', args: {}, pid: 52, ts: 19000, cat: 'foo', tid: 53, ph: 'E'},
    {name: 'b', args: {}, pid: 52, ts: 32000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'b', args: {}, pid: 52, ts: 54000, cat: 'foo', tid: 53, ph: 'E'}
  ]);

  var systemTraceTestData = [
    'systrace.sh-8170  [000] 0.013: sched_switch: ' +
        'prev_comm=systrace.sh prev_pid=8170 prev_prio=120 ' +
        'prev_state=x ==> next_comm=kworker/1:0 next_pid=7873 ' +
        'next_prio=120',
    ' kworker/1:0-7873  [000] 0.036: sched_switch: ' +
        'prev_comm=kworker/1:0 prev_pid=7873 prev_prio=120 ' +
        'prev_state=S ==> next_comm=debugd next_pid=4404 ' +
        'next_prio=120',
    '     debugd-4404  [000] 0.070: sched_switch: prev_comm=debugd ' +
        'prev_pid=4404 prev_prio=120 prev_state=S ==> ' +
        'next_comm=dbus-daemon next_pid=510 next_prio=120',
    'systrace.sh-8182  [000] 0.000: tracing_mark_write: ' +
        'trace_event_clock_sync: parent_ts=0.0'
  ].join('\n');

  // This code emulates Chrome's responses to sendFn enough that the real
  // tracing controller can be used to interactively test the UI.
  var createSendHandler = function() {
    var systemTraceRequested = false;
    var corruptTrace;
    var tracingController;
    function send(message, opt_args) {
      var args = opt_args || [];
      if (message == 'getKnownCategories') {
        setTimeout(function() {
          tracingController.onKnownCategoriesCollected(['a', 'b', 'c']);
        }, 1);

      } else if (message == 'beginTracing') {
        systemTraceRequested = opt_args[0];
        continuousTraceRequested = opt_args[1];
        samplingRequested = opt_args[2];

      } else if (message == 'beginRequestBufferPercentFull') {
        setTimeout(function() {
          tracingController.onRequestBufferPercentFullComplete(0.5);
        }, 1);

      } else if (message == 'endTracingAsync') {
        setTimeout(function() {
          if (systemTraceRequested) {
            tracingController.onSystemTraceDataCollected(systemTraceTestData);
          }

          // Strip off [] and add a ,
          var n = testDataString.length - 1;
          var tmp = testDataString.substr(1, n - 1) + ',';
          if (corruptTrace)
            tmp += 'corruption';
          tracingController.onEndTracingComplete(tmp);
        }, 1);

      } else if (message == 'loadTraceFile') {
        setTimeout(function() {
          var tmp = testDataString.substr(0);
          if (corruptTrace)
            tmp += 'corruption';
          tracingController.onLoadTraceFileComplete(tmp);
        }, 150);

      } else if (message == 'saveTraceFile') {
        setTimeout(function() {
          tracingController.onSaveTraceFileComplete();
        }, 1);
      }
    }

    send.__defineSetter__('tracingController', function(c) {
      tracingController = c;
    });

    send.__defineSetter__('corruptTrace', function(c) {
      corruptTrace = c;
    });
    return send;
  };

  /*
   * Just enough of the TracingController to support the tests below.
   */
  var FakeTracingController = function() {
    this.wasBeginTracingCalled = false;
    this.wasCollectCategoriesCalled = false;
    this.wasSamplingEnabled = false;
  };

  FakeTracingController.prototype = {
    __proto__: base.EventTarget.prototype,

    get supportsSystemTracing() {
      return base.isChromeOS;
    },

    beginTracing: function(opt_systemTracingEnabled,
                           opt_continuousTracingEnabled,
                           opt_enableSampling,
                           opt_traceCategories) {
      this.wasBeginTracingCalled = true;
      this.wasBeginTracingCalledWithSystemTracingEnabled =
          opt_systemTracingEnabled;
      this.wasBeginTracingCalledWithContinuousTracingEnabled =
          opt_continuousTracingEnabled;
      this.beginTracingCategories = opt_traceCategories;
      this.wasSamplingEnabled = opt_enableSampling;
    },

    collectCategories: function() {
      this.wasCollectCategoriesCalled = true;
    },

    get traceEventData() {
      if (!this.wasBeginTracingCalled)
        return undefined;
      return testDataString;
    },

    get systemTraceEvents() {
      if (!this.wasBeginTracingCalled)
        return [];
      if (!this.wasBeginTracingCalledWithSystemTracingEnabled)
        return [];
      return systemTraceTestData;
    },

    set tracingEnabled(val) {
      this.isTracingEnabled_ = val;
    },

    get isTracingEnabled() {
      if (this.isTracingEnabled_ === undefined)
        this.isTracingEnabled_ = false;
      return this.isTracingEnabled_;
    }
  };

  var recordTestCommon = function() {
    var view = new about_tracing.ProfilingView();

    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;

    view.querySelector('button.record').click();
    assertTrue(tracingController.wasCollectCategoriesCalled);

    var e = new base.Event('categoriesCollected');
    e.categories = ['skia', 'gpu'];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    assertTrue(tracingController.wasBeginTracingCalled);
    assertEquals(base.isChromeOS,
        tracingController.wasBeginTracingCalledWithSystemTracingEnabled);

    var e = new base.Event('traceEnded');
    e.events = tracingController.traceEventData;
    tracingController.dispatchEvent(e);

    assertTrue(!!view.timelineView.model);
    view.detach_();
  };

  test('instantiate', function() {
    var parent = document.createElement('div');
    this.addHTMLOutput(parent);

    var view = new about_tracing.ProfilingView();
    parent.appendChild(view);

    var sendHandler = createSendHandler();
    var tracingController = new about_tracing.TracingController(sendHandler);
    sendHandler.tracingController = tracingController;
    tracingController.supportsSystemTracing_ = true;

    view.tracingController = tracingController;
    view.focusElement = view;
    parent.appendChild(ui.createCheckBox(sendHandler, 'corruptTrace',
                                         'profilingViewTest.corruptTrace',
                                         false, 'Make traces corrupt'));
    view.detach_();
  });

  test('selectedCategoriesSentToTracing', function() {
    var view = new about_tracing.ProfilingView();
    view.timelineView_.settings.set('cc', true, 'record_categories');
    view.timelineView_.settings.set('renderer', false, 'record_categories');

    var tracingController = new FakeTracingController(this);
    view.tracingController = tracingController;

    view.querySelector('button.record').click();
    assertTrue(tracingController.wasCollectCategoriesCalled);

    var e = new base.Event('categoriesCollected');
    e.categories = ['skia', 'gpu', 'cc', 'renderer'];
    tracingController.dispatchEvent(e);

    assertVisible(view.recordSelectionDialog_);
    assertVisible(view.recordSelectionDialog_.toolbar);

    view.recordSelectionDialog_.querySelector('input#skia').click();
    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    var categories = tracingController.beginTracingCategories;
    // Renderer is disabled in settings, skia is clicked off.
    assertEquals('-renderer,-skia', categories);

    view.detach_();
  });

  test('badCategories', function() {
    var view = new about_tracing.ProfilingView();
    view.timelineView_.settings.set('foo,bar', false, 'record_categories');

    var tracingController = new FakeTracingController(this);
    view.tracingController = tracingController;

    view.querySelector('button.record').click();
    assertTrue(tracingController.wasCollectCategoriesCalled);

    var e = new base.Event('categoriesCollected');
    e.categories = ['baz,zap', 'gpu'];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    var inputs = view.recordSelectionDialog_.querySelectorAll('input');
    var inputs_length = inputs.length;
    for (var i = 0; i < inputs_length; ++i) {
      // Comes from categories and should be split before getting
      // to the record selection dialog.
      assertNotEquals('baz,zap', inputs[i].id);
    }
    var categories = tracingController.beginTracingCategories;
    assertEquals('', categories);

    view.detach_();
  });

  test('recordNonCros', function() {
    var old = base.isChromeOS;
    base.isChromeOS = false;
    try {
      recordTestCommon();
    } finally {
      base.isChromeOS = old;
    }
  });

  test('recordCros', function() {
    var old = base.isChromeOS;
    base.isChromeOS = true;
    try {
      recordTestCommon();
    } finally {
      base.isChromeOS = old;
    }
  });

  test('recordWithTraceRunning_KeyEvent', function() {
    var view = new about_tracing.ProfilingView();
    var tracingController = new FakeTracingController();
    tracingController.tracingEnabled = true;
    view.tracingController = tracingController;

    var evt = document.createEvent('Event');
    evt.initEvent('keypress',
        true,  //  canBubbleArg
        true,  //  cancelableArg
        window);  //  viewArg
    evt.keyCode = 'r'.charCodeAt(0);

    document.dispatchEvent(evt);
    assertFalse(tracingController.wasCollectCategoriesCalled);

    view.detach_();
  });

  test('categorySelectionWithTraceRunning_KeyEvent', function() {
    var view = new about_tracing.ProfilingView();
    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;
    view.selectingCategories = true;

    var evt = document.createEvent('Event');
    evt.initEvent('keypress',
        true,  //  canBubbleArg
        true,  //  cancelableArg
        window);  //  viewArg
    evt.keyCode = 'r'.charCodeAt(0);

    document.dispatchEvent(evt);
    assertFalse(tracingController.wasCollectCategoriesCalled);

    view.detach_();
  });

  test('categorySelectionSetsSelectingCategories', function() {
    var view = new about_tracing.ProfilingView();
    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;
    view.selectingCategories = false;

    view.querySelector('button.record').click();
    assertTrue(view.selectingCategories);

    var e = new base.Event('categoriesCollected');
    e.categories = ['skia', 'gpu', 'cc', 'renderer'];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    assertFalse(view.selectingCategories);
    view.detach_();
  });

  test('categorySelectionResetsSelectingCategoriesOnDialogDismiss', function() {
    var view = new about_tracing.ProfilingView();
    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;
    view.selectingCategories = false;

    view.querySelector('button.record').click();
    assertTrue(view.selectingCategories);

    var e = new base.Event('categoriesCollected');
    e.categories = ['skia', 'gpu', 'cc', 'renderer'];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.visible = false;

    assertFalse(view.selectingCategories);
    view.detach_();
  });

  test('recording_withSamplingEnabled', function() {
    var view = new about_tracing.ProfilingView();

    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;
    view.querySelector('button.record').click();

    var e = new base.Event('categoriesCollected');
    e.categories = [];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.querySelector('.sampling-button').click();
    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    assertTrue(tracingController.wasBeginTracingCalled);
    assertTrue(tracingController.wasSamplingEnabled);
  });

  test('recording_withSamplingDisabled', function() {
    var view = new about_tracing.ProfilingView();

    var tracingController = new FakeTracingController();
    view.tracingController = tracingController;
    view.querySelector('button.record').click();

    var e = new base.Event('categoriesCollected');
    e.categories = [];
    tracingController.dispatchEvent(e);

    view.recordSelectionDialog_.querySelector(
        'button.record-categories').click();

    assertTrue(tracingController.wasBeginTracingCalled);
    assertFalse(tracingController.wasSamplingEnabled);
  });
});
