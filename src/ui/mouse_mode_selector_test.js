// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.mouse_mode_selector');

base.unittest.testSuite('ui.mouse_mode_selector', function() {
  test('instantiate', function() {
    var sel = new ui.MouseModeSelector();
    this.addHTMLOutput(sel);
  });

});
