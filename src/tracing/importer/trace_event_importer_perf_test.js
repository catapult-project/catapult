// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.trace_event_importer');

base.unittest.testSuite('tracing.importer.trace_event_importer_perf_test', function() { // @suppress longLineCheck
  var eventStrings = {};

  function getSynchronous(url) {
    var req = new XMLHttpRequest();
    req.open('GET', url, false);
    req.send(null);
    return req.responseText;
  }

  function getEvents(url) {
    if (url in eventStrings)
      return eventStrings[url];
    eventStrings[url] = getSynchronous(url);
    return eventStrings[url];
  }

  function timedPerfTestWithEvents(name, testFn, initialOptions) {
    if (initialOptions.setUp)
      throw new Error(
          'Per-test setUp not supported. Trivial to fix if needed.');

    var options = {};
    for (var k in initialOptions)
      options[k] = initialOptions[k];
    options.setUp = function() {
      ['/test_data/simple_trace.json', '/test_data/lthi_cats.json'].forEach(
          function warmup(url) {
            getEvents(url);
          });
    };
    timedPerfTest(name, testFn, options);
  }

  var n110100 = [1, 10, 100];
  n110100.forEach(function(val) {
    timedPerfTestWithEvents('simple_trace_' + val, function() {
      var events = getEvents('/test_data/simple_trace.json');
      var m = new tracing.TraceModel();
      m.importTraces([events], false, false);
    }, {iterations: val});
  });

  timedPerfTestWithEvents('lthi_cats_1', function() {
    var events = getEvents('/test_data/lthi_cats.json');
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);
  }, {iterations: 1});
});
