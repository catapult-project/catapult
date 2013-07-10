// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.filter_control');

base.unittest.testSuite('ui.filter_control', function() {
  var filterControl = new ui.FilterControl();

  setup(function() {
    document.body.appendChild(filterControl);
  });

  teardown(function() {
    document.body.removeChild(filterControl);
  });

  test('filterControl', function() {
    filterControl.addEventListener('filterTextChange', function(event) {
      filterControl.hitCountText =
          event.oldValue.length + ' to ' + event.newValue.length;
    }.bind(this));

    filterControl.focus();
    filterControl.hitCountText = '0 of 0';
    filterControl.blur();
    filterControl.focus();

    var event = new CustomEvent('input');
    filterControl.querySelector('input').value = 'd';
    filterControl.querySelector('input').dispatchEvent(event);

    assertTrue(filterControl.filterText === 'd');
    assertTrue(filterControl.hitCountText = '0 to 1');
  });
});
