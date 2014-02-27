// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('telemetry.web_components.results_viewer');

tvcm.unittest.testSuite('telemetry.web_components.results_viewer_unittest',
    function() {
      test('testBasic', function() {
        var resultsViewer = new telemetry.web_components.ResultsViewer();
        resultsViewer.dataToView = {hello: 'world', nice: ['to', 'see', 'you']};
        this.addHTMLOutput(resultsViewer);
      });
    });
