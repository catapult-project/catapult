// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.record_selection_dialog');

base.exportTo('about_tracing', function() {
  function beginRequest(method, path, data) {
    if (data === undefined)
      data = null;
    return new Promise(function(resolver) {
      var req = new XMLHttpRequest();
      if (method != 'POST' && data !== null)
        throw new Error('Non-POST should have data==null');
      req.open(method, path, true);
      req.onreadystatechange = function(e) {
        if (req.readyState == 4) {
          window.setTimeout(function() {
            if (req.status == 200) {
              resolver.resolve(req.responseText);
            } else {
              resolver.reject(new Error('At ' + path + ' error ' + req.status));
            }
          }, 0);
        }
      };
      req.send(data);
    });
  }

  function beginRecording(beginRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });
    finalPromise.selectionDlg = undefined;
    finalPromise.progressDlg = undefined;

    function beginRecordingError(err) {
      finalPromiseResolver.reject(err);
    }

    // Step 1: Get categories.
    beginRequest('GET', '/json/categories').then(
        showTracingDialog,
        beginRecordingError);


    // Step 2: Show tracing dialog.
    var selectionDlg;
    function showTracingDialog(categoriesString) {
      var categories = JSON.parse(categoriesString);
      selectionDlg = new tracing.RecordSelectionDialog();
      selectionDlg.categories = categories;
      selectionDlg.settings_key = 'about_tracing.record_selection_dialog';
      selectionDlg.addEventListener('recordclick', startTracing);
      selectionDlg.addEventListener('closeclick', cancelRecording);
      selectionDlg.visible = true;

      finalPromise.selectionDlg = selectionDlg;
    }

    function cancelRecording() {
      finalPromise.selectionDlg = undefined;
      finalPromiseResolver.reject(new UserCancelledError());
    }

    // Step 2: Do the actual tracing dialog.
    var progressDlg;
    var bufferPercentFullDiv;
    function startTracing() {
      progressDlg = new ui.Overlay();
      progressDlg.textContent = 'Recording...';
      progressDlg.userCanClose = false;

      bufferPercentFullDiv = document.createElement('div');
      progressDlg.appendChild(bufferPercentFullDiv);

      var stopButton = document.createElement('button');
      stopButton.textContent = 'Stop';
      progressDlg.clickStopButton = function() {
        stopButton.click();
      };
      progressDlg.appendChild(stopButton);

      var recordingOptions = {
        categoryFilter: selectionDlg.categoryFilter(),
        useSystemTracing: selectionDlg.useSystemTracing,
        useContinuousTracing: selectionDlg.useContinuousTracing,
        useSampling: selectionDlg.useSampling
      };


      var recordingOptionsB64 = btoa(JSON.stringify(recordingOptions));
      var requestPromise = beginRequest('GET', '/json/begin_recording?' +
                                        recordingOptionsB64);
      requestPromise.then(
          function() {
            progressDlg.visible = true;
            stopButton.focus();
            updateBufferPercentFull('0');
          },
          recordFailed);

      stopButton.addEventListener('click', function() {
        var recordingPromise = beginRequest('GET', '/json/end_recording');
        recordingPromise.then(
            recordFinished,
            recordFailed);
        bufferPercentFullDiv = undefined;
      });
      finalPromise.progressDlg = progressDlg;
    }

    function recordFinished(tracedData) {
      progressDlg.visible = false;
      finalPromise.progressDlg = undefined;
      finalPromiseResolver.resolve(tracedData);
    }

    function recordFailed(err) {
      progressDlg.visible = false;
      finalPromise.progressDlg = undefined;
      finalPromiseResolver.reject(err);
    }

    function getBufferPercentFull() {
      if (!bufferPercentFullDiv)
        return;

      beginRequest('GET', '/json/get_buffer_percent_full').then(
          updateBufferPercentFull);
    }

    function updateBufferPercentFull(percent_full) {
      if (!bufferPercentFullDiv)
        return;

      percent_full = parseFloat(percent_full);
      var newText = 'Buffer usage: ' + Math.round(100 * percent_full) + '%';
      if (bufferPercentFullDiv.textContent != newText)
        bufferPercentFullDiv.textContent = newText;

      window.setTimeout(getBufferPercentFull, 500);
    }

    // Thats it! We're done.
    return finalPromise;
  };

  function UserCancelledError() {
    Error.apply(this, arguments);
  }
  UserCancelledError.prototype = {
    __proto__: Error.prototype
  };

  return {
    beginRequest: beginRequest,
    beginRecording: beginRecording,
    UserCancelledError: UserCancelledError
  };
});
