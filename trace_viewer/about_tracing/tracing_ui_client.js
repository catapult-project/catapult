// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.record_selection_dialog');

tvcm.exportTo('about_tracing', function() {
  function tracingRequest(method, path, data) {
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
            if (req.status == 200 && req.responseText != '##ERROR##') {
              resolver.resolve(req.responseText);
            } else {
              resolver.reject(new Error('Error occured at ' + path));
            }
          }, 0);
        }
      };
      req.send(data);
    });
  }

  function beginMonitoring(tracingRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });

    // TODO(haraken): Implement a configure dialog to set these options.
    var monitoringOptions = {
      categoryFilter: '*',
      useSystemTracing: false,
      useContinuousTracing: false,
      useSampling: true
    };

    var monitoringOptionsB64 = btoa(JSON.stringify(monitoringOptions));
    var beginMonitoringPromise = tracingRequest(
        'GET', '/json/begin_monitoring?' + monitoringOptionsB64);
    beginMonitoringPromise.then(
        function() {
          finalPromiseResolver.resolve();
        },
        function(err) {
          finalPromiseResolver.reject(err);
        });

    return finalPromise;
  }

  function endMonitoring(tracingRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });

    var endMonitoringPromise = tracingRequest('GET', '/json/end_monitoring');
    endMonitoringPromise.then(
        function() {
          finalPromiseResolver.resolve();
        },
        function(err) {
          finalPromiseResolver.reject(err);
        });

    return finalPromise;
  }

  function captureMonitoring(tracingRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });

    var captureMonitoringPromise =
        tracingRequest('GET', '/json/capture_monitoring');
    captureMonitoringPromise.then(
        captureMonitoringResolved,
        captureMonitoringRejected);

    function captureMonitoringResolved(tracedData) {
      finalPromiseResolver.resolve(tracedData);
    }

    function captureMonitoringRejected(err) {
      finalPromiseResolver.reject(err);
    }

    return finalPromise;
  }

  function getMonitoringStatus(tracingRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });

    var getMonitoringStatusPromise =
        tracingRequest('GET', '/json/get_monitoring_status');
    getMonitoringStatusPromise.then(
        function(monitoringOptionsBase64) {
          var monitoringOptions = JSON.parse(atob(monitoringOptionsBase64));
          finalPromiseResolver.resolve(monitoringOptions.isMonitoring,
                                       monitoringOptions.categoryFilter,
                                       monitoringOptions.useSystemTracing,
                                       monitoringOptions.useContinuousTracing,
                                       monitoringOptions.useSampling);
        },
        function(err) {
          finalPromiseResolver.reject(err);
        });

    return finalPromise;
  }

  function beginRecording(tracingRequest) {
    var finalPromiseResolver;
    var finalPromise = new Promise(function(resolver) {
      finalPromiseResolver = resolver;
    });
    finalPromise.selectionDlg = undefined;
    finalPromise.progressDlg = undefined;

    function beginRecordingError(err) {
      finalPromiseResolver.reject(err);
    }

    // Step 0: End recording. This is necessary when the user reloads the
    // about:tracing page when we are recording. Window.onbeforeunload is not
    // reliable to end recording on reload.
    endRecording(tracingRequest).then(
        getCategories,
        getCategories);  // Ignore error.

    // Step 1: Get categories.
    function getCategories() {
      tracingRequest('GET', '/json/categories').then(
          showTracingDialog,
          beginRecordingError);
    }

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
      progressDlg = new tvcm.ui.Overlay();
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
      var requestPromise = tracingRequest('GET', '/json/begin_recording?' +
                                          recordingOptionsB64);
      requestPromise.then(
          function() {
            progressDlg.visible = true;
            stopButton.focus();
            updateBufferPercentFull('0');
          },
          recordFailed);

      stopButton.addEventListener('click', function() {
        var recordingPromise = endRecording(tracingRequest);
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

      tracingRequest('GET', '/json/get_buffer_percent_full').then(
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

  function endRecording(tracingRequest) {
    return tracingRequest('GET', '/json/end_recording');
  }

  function UserCancelledError() {
    Error.apply(this, arguments);
  }
  UserCancelledError.prototype = {
    __proto__: Error.prototype
  };

  window.onbeforeunload = function(e) {
    endRecording(tracingRequest);
  }

  return {
    tracingRequest: tracingRequest,
    beginRecording: beginRecording,
    beginMonitoring: beginMonitoring,
    endMonitoring: endMonitoring,
    captureMonitoring: captureMonitoring,
    getMonitoringStatus: getMonitoringStatus,
    UserCancelledError: UserCancelledError
  };
});
