// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.trace_event_importer');

base.unittest.testSuite('tracing.importer.trace_event_importer_perf', function() { // @suppress longLineCheck
  var eventStrings = {};

  function getSynchronous(url) {
    var req = new XMLHttpRequest();
    req.open('GET', url, false);
    req.send(null);
    return req.responseText;
  }

  function getEvents(url) {
    if (!(url in eventStrings))
      throw new Error('Missing events for given URL: ' + url);
    return eventStrings[url];
  }

  setupOnce(function() {
    var urls = ['../test_data/simple_trace.json',
                '../test_data/lthi_cats.json'];

    for (var i = 0; i < urls.length; ++i)
      eventStrings[urls[i]] = getSynchronous(urls[i]);
  });

  perf_test('simple_trace', [1, 10, 100], function() {
    var events = getEvents('../test_data/simple_trace.json');
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);
  });

  perf_test('lthi_cats', [1, 10], function() {
    var events = getEvents('../test_data/lthi_cats.json');
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);
  });
});
