// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('about_tracing.mock_request_handler');
tvcm.require('about_tracing.tracing_ui_client');

tvcm.unittest.testSuite('about_tracing.tracing_ui_client_test', function() {
  var testData = [
    {name: 'a', args: {}, pid: 52, ts: 15000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'a', args: {}, pid: 52, ts: 19000, cat: 'foo', tid: 53, ph: 'E'},
    {name: 'b', args: {}, pid: 52, ts: 32000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'b', args: {}, pid: 52, ts: 54000, cat: 'foo', tid: 53, ph: 'E'}
  ];

  test('fullRecording', function() {
    return new Promise(function(r) {
      var mock = new about_tracing.MockRequestHandler();
      mock.expectRequest('GET', '/json/end_recording', function() {
        return '';
      });
      mock.expectRequest('GET', '/json/categories', function() {
        setTimeout(function() {
          recordingPromise.selectionDlg.clickRecordButton();
        }, 20);
        return JSON.stringify(['a', 'b', 'c']);
      });
      mock.expectRequest('GET', '/json/begin_recording', function(data, path) {
        var optionsB64 = path.match(/\/json\/begin_recording\?(.+)/)[1];
        var recordingOptions = JSON.parse(atob(optionsB64));
        assertTrue(typeof recordingOptions.categoryFilter === 'string');
        assertTrue(typeof recordingOptions.useSystemTracing === 'boolean');
        assertTrue(typeof recordingOptions.useSampling === 'boolean');
        assertTrue(typeof recordingOptions.useContinuousTracing === 'boolean');
        setTimeout(function() {
          recordingPromise.progressDlg.clickStopButton();
        }, 10);
        return '';
      });
      mock.expectRequest('GET', '/json/end_recording', function(data) {
        return JSON.stringify(testData);
      });

      var recordingPromise = about_tracing.beginRecording(
          mock.tracingRequest.bind(mock));

      return recordingPromise.then(
          function(data) {
            mock.assertAllRequestsHandled();
            var testDataString = JSON.stringify(testData);
            assertEquals(testDataString, data);
            r.resolve();
          },
          function(error) {
            r.reject('This should never be reached');
          });
    });
  });

  test('monitoring', function() {
    return new Promise(function(r) {
      var mock = new about_tracing.MockRequestHandler();
      var tracingRequest = mock.tracingRequest.bind(mock);

      mock.expectRequest('GET', '/json/begin_monitoring', function(data, path) {
        var optionsB64 = path.match(/\/json\/begin_monitoring\?(.+)/)[1];
        var monitoringOptions = JSON.parse(atob(optionsB64));
        assertTrue(typeof monitoringOptions.categoryFilter === 'string');
        assertTrue(typeof monitoringOptions.useSystemTracing === 'boolean');
        assertTrue(typeof monitoringOptions.useSampling === 'boolean');
        assertTrue(typeof monitoringOptions.useContinuousTracing === 'boolean');
        setTimeout(function() {
          var capturePromise = about_tracing.captureMonitoring(tracingRequest);
          capturePromise.then(
              function(data) {
                var testDataString = JSON.stringify(testData);
                assertEquals(testDataString, data);
              },
              function(error) {
                r.reject();
              });
        }, 10);
        return '';
      });

      mock.expectRequest('GET', '/json/capture_monitoring', function(data) {
        setTimeout(function() {
          var endPromise = about_tracing.endMonitoring(tracingRequest);
          endPromise.then(
              function(data) {
                mock.assertAllRequestsHandled();
                r.resolve();
              },
              function(error) {
                r.reject();
              });
        }, 10);
        return JSON.stringify(testData);
      });

      mock.expectRequest('GET', '/json/end_monitoring', function(data) {
      });

      about_tracing.beginMonitoring(tracingRequest);
    });
  });
});
