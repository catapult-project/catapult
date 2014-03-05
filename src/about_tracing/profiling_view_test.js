// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('about_tracing.mock_request_handler');
tvcm.require('about_tracing.profiling_view');

tvcm.unittest.testSuite('about_tracing.profiling_view_test', function() {

  var testData = [
    {name: 'a', args: {}, pid: 52, ts: 15000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'a', args: {}, pid: 52, ts: 19000, cat: 'foo', tid: 53, ph: 'E'},
    {name: 'b', args: {}, pid: 52, ts: 32000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'b', args: {}, pid: 52, ts: 54000, cat: 'foo', tid: 53, ph: 'E'}
  ];

  var monitoringOptions = {
    isMonitoring: false,
    categoryFilter: '*',
    useSystemTracing: false,
    useContinuousTracing: false,
    useSampling: false
  };

  var ProfilingView = about_tracing.ProfilingView;

  test('recording', function() {

    var mock = new about_tracing.MockRequestHandler();
    mock.allowLooping = true;
    mock.expectRequest('GET', '/json/get_monitoring_status', function() {
      return btoa(JSON.stringify(monitoringOptions));
    });
    mock.expectRequest('GET', '/json/end_recording', function() {
      return '';
    });
    mock.expectRequest('GET', '/json/categories', function() {
      return JSON.stringify(['a', 'b', 'c']);
    });
    mock.expectRequest('GET', '/json/begin_recording', function(data) {
      return '';
    });
    mock.expectRequest('GET', '/json/end_recording', function(data) {
      return JSON.stringify(testData);
    });

    var view = new ProfilingView(mock.tracingRequest.bind(mock));
    view.style.height = '400px';
    view.style.border = '1px solid black';
    this.addHTMLOutput(view);

    return new Promise(function(resolver) {
      var recordingPromise = view.beginRecording();
      function pressRecord() {
        recordingPromise.selectionDlg.clickRecordButton();
        setTimeout(pressStop, 60);
      }
      function pressStop() {
        recordingPromise.progressDlg.clickStopButton();
      }
      setTimeout(pressRecord, 60);
      recordingPromise.then(
          function() {
            resolver.resolve();
          },
          function() {
            resolver.reject();
          });
    });
  });

  test('monitoring', function() {

    var mock = new about_tracing.MockRequestHandler();
    mock.allowLooping = true;
    mock.expectRequest('GET', '/json/get_monitoring_status', function() {
      return btoa(JSON.stringify(monitoringOptions));
    });
    mock.expectRequest('GET', '/json/begin_monitoring', function(data) {
      return '';
    });
    mock.expectRequest('GET', '/json/capture_monitoring', function(data) {
      return JSON.stringify(testData);
    });
    mock.expectRequest('GET', '/json/end_monitoring', function(data) {
      return '';
    });

    var view = new ProfilingView(mock.tracingRequest.bind(mock));
    view.style.height = '400px';
    view.style.border = '1px solid black';
    this.addHTMLOutput(view);

    return new Promise(function(resolver) {
      var buttons = view.querySelector('x-timeline-view-buttons');
      assertEquals(buttons.querySelector('#monitor-checkbox').checked, false);

      function beginMonitoring() {
        // Since we don't fall back to TracingController when testing,
        // we cannot rely on TracingController to invoke a callback to change
        // view.isMonitoring_. Thus we change view.isMonitoring_ manually.
        view.onMonitoringStateChanged_(true);
        assertEquals(buttons.querySelector('#monitor-checkbox').checked, true);
        setTimeout(captureMonitoring, 60);
      }

      function captureMonitoring() {
        assertEquals(buttons.querySelector('#monitor-checkbox').checked, true);
        buttons.querySelector('#capture-button').click();
        setTimeout(endMonitoring, 60);
      }
      function endMonitoring() {
        assertEquals(buttons.querySelector('#monitor-checkbox').checked, true);
        buttons.querySelector('#monitor-checkbox').click();
        assertEquals(buttons.querySelector('#monitor-checkbox').checked, false);
      }

      var monitoringPromise = view.beginMonitoring();
      setTimeout(beginMonitoring, 60);

      monitoringPromise.then(
          resolver.resolve.bind(resolver),
          resolver.reject.bind(resolver));
    });
  });
});
