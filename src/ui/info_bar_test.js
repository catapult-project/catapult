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

  test('group-instantiate', function() {
    var infoBarGroup = new ui.InfoBarGroup();
    infoBarGroup.addMessage(
        'Message 1',
        [{buttonText: 'ok', onClick: function() {}}]);
    infoBarGroup.addMessage(
        'Message 2',
        [{buttonText: 'button 2', onClick: function() {}}]);
    this.addHTMLOutput(infoBarGroup);
  });

  test('group-populate-then-clear', function() {
    var infoBarGroup = new ui.InfoBarGroup();
    infoBarGroup.addMessage(
        'Message 1',
        [{buttonText: 'ok', onClick: function() {}}]);
    infoBarGroup.addMessage(
        'Message 2',
        [{buttonText: 'button 2', onClick: function() {}}]);
    infoBarGroup.clearMessages();
    assertEquals(0, infoBarGroup.children.length);
  });

  test('group-populate-clear-repopulate', function() {
    var infoBarGroup = new ui.InfoBarGroup();
    infoBarGroup.addMessage(
        'Message 1',
        [{buttonText: 'ok', onClick: function() {}}]);
    infoBarGroup.addMessage(
        'Message 2',
        [{buttonText: 'button 2', onClick: function() {}}]);
    infoBarGroup.clearMessages();
    infoBarGroup.addMessage(
        'Message 1',
        [{buttonText: 'ok', onClick: function() {}}]);
    this.addHTMLOutput(infoBarGroup);
  });
});
