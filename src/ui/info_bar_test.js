// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.info_bar');

base.unittest.testSuite('ui.info_bar', function() {
  test('instantiate', function() {
    var infoBar = new ui.InfoBar();
    infoBar.message = 'This is an info';
    infoBar.visible = true;
    this.addHTMLOutput(infoBar);
  });

  test('buttons', function() {
    var infoBar = new ui.InfoBar();
    infoBar.visible = true;
    infoBar.message = 'This is an info bar with buttons';
    var didClick = false;
    var button = infoBar.addButton('More info...', function() {
      didClick = true;
    });
    button.click();
    assertTrue(didClick);
    this.addHTMLOutput(infoBar);
  });
});
