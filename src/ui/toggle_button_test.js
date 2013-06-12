// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('ui.toggle_button');

'use strict';

base.unittest.testSuite('ui.toggle_button', function() {
  test('toggleButton', function() {
    var testTarget = new ui.ToggleButton();

    assertTrue(testTarget.isOn);

    var newValue;
    testTarget.addEventListener('isOnChange', function(event) {
      newValue = event.newValue;
    });

    assertTrue(testTarget.isOn);  // initially true

    testTarget.click();
    assertTrue(!testTarget.isOn);  // property tracks
    assertTrue(!newValue);           // event fires

    testTarget.click();
    assertTrue(testTarget.isOn);  // property toggles
    assertTrue(newValue);           // event fires and toggles
  });
});
