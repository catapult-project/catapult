// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.mouse_mode_selector');

base.unittest.testSuite('ui.mouse_mode_selector', function() {
  var MOUSE_SELECTOR_MODE = ui.MOUSE_SELECTOR_MODE;
  test('instantiate', function() {
    var sel = new ui.MouseModeSelector();
    sel.supportedModeMask =
        MOUSE_SELECTOR_MODE.SELECTION |
        MOUSE_SELECTOR_MODE.PANSCAN;
    this.addHTMLOutput(sel);
  });

  test('changeMaskWithUnsupportedMode', function() {
    var sel = new ui.MouseModeSelector();
    sel.mode = MOUSE_SELECTOR_MODE.SELECTION;
    assertThrows(function() {
      sel.supportedModeMask = MOUSE_SELECTOR_MODE.ZOOM;
    });
  });

  test('modePersists', function() {
    var sel1 = new ui.MouseModeSelector();
    sel1.defaultMode_ = MOUSE_SELECTOR_MODE.ZOOM;
    sel1.settingsKey = 'foo';
    assertEquals(MOUSE_SELECTOR_MODE.ZOOM, sel1.mode);

    sel1.mode = MOUSE_SELECTOR_MODE.PANSCAN;

    var sel2 = new ui.MouseModeSelector();
    sel2.settingsKey = 'foo';
    assertEquals(MOUSE_SELECTOR_MODE.PANSCAN, sel2.mode);
  });

});
