// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
tvcm.require('tvcm.key_event_manager');
tvcm.require('tvcm.promise');
tvcm.require('tvcm.settings');
tvcm.require('tvcm.unittest.test_error');
tvcm.require('tvcm.unittest.assertions');
tvcm.require('tvcm.unittest.suite_loader');
tvcm.require('tvcm.unittest.test_case');
tvcm.require('tvcm.unittest.test_suite');
tvcm.require('tvcm.unittest.test_runner');

tvcm.exportTo('tvcm.unittest', function() {
  // Manually export tvcm.unittest.testSuite to the tvcm namespace. This is done
  // to avoid linewrapping in 80col-constrained environments.
  tvcm.testSuite = tvcm.unittest.testSuite;

  return {
  };
});
