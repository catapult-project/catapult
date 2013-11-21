// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('about_tracing.mock_request_handler');
base.require('about_tracing.profiling_view');

base.unittest.testSuite('about_tracing.profiling_view', function() {

  var testData = [
    {name: 'a', args: {}, pid: 52, ts: 15000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'a', args: {}, pid: 52, ts: 19000, cat: 'foo', tid: 53, ph: 'E'},
    {name: 'b', args: {}, pid: 52, ts: 32000, cat: 'foo', tid: 53, ph: 'B'},
    {name: 'b', args: {}, pid: 52, ts: 54000, cat: 'foo', tid: 53, ph: 'E'}
  ];

  var ProfilingView = about_tracing.ProfilingView;

  test('instantiate', function() {

    var mock = new about_tracing.MockRequestHandler();
    mock.allowLooping = true;
    mock.expectRequest('GET', '/json/categories', function() {
      return JSON.stringify(['a', 'b', 'c']);
    });
    mock.expectRequest('GET', '/json/begin_recording', function(data) {
      return '';
    });
    mock.expectRequest('GET', '/json/end_recording', function(data) {
      return JSON.stringify(testData);
    });

    var view = new ProfilingView();
    view.beginRequestImpl = mock.beginRequest.bind(mock);
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
          resolver.resolve.bind(resolver),
          resolver.reject.bind(resolver));
    });
  });

});
