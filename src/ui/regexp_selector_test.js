// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('ui');
base.require('ui.regexp_selector');

'use strict';

base.unittest.testSuite('ui.regexp_selector', function() {
  test('regExpSelector', function() {
    var div = document.createElement('div');
    document.body.appendChild(div);

    var regExpSelector = new ui.RegExpSelector();
    div.appendChild(regExpSelector);

    var matchBits = function(items) {
      return items.map(function(item) {return item.matches ? '1' : '0';});
    }

    var stringsToFilter = [
      'foo',
      'baz',
      'bax'
    ];

    // Initial value is default.
    assertEquals(regExpSelector.regexp.source, ui.RegExpSelector.defaultSource);

    // Off by default.
    assertTrue(!regExpSelector.isOn);

    stringsToFilter.forEach(
        regExpSelector.addFilterableItem.bind(regExpSelector)
    );
    regExpSelector.isOn = true;

    var filterControl = regExpSelector.querySelector('.filter-control');

    // Initally all items match.
    assertEquals(matchBits(regExpSelector.items).toString(), '1,1,1');
    assertEquals(filterControl.hitCountText, '3 of 3');

    regExpSelector.isOn = false;

    // Inactive selector selects none.
    assertEquals(matchBits(regExpSelector.items).toString(), '0,0,0');

    filterControl.filterText = 'ba';

    // Moving from blank to non-blank turns on the selector.
    assertTrue(regExpSelector.isOn);

    // 2nd & 3rd match.
    assertEquals(matchBits(regExpSelector.items).toString(), '0,1,1');
    assertEquals(filterControl.hitCountText, '2 of 3');

    filterControl.filterText = '';

    // Blank text gives default RegExp.
    assertEquals(regExpSelector.regexp.source, ui.RegExpSelector.defaultSource);

    // Default RegExp gives blank text.
    assertFalse(regExpSelector.querySelector('input').value);

    // Blank regexp are not on.
    assertFalse(regExpSelector.isOn);

    regExpSelector.regexp = /ba/;

    // Update through API gives same results as UI.
    assertTrue(regExpSelector.isOn);
    assertEquals(matchBits(regExpSelector.items).toString(), '0,1,1');
    assertEquals(filterControl.hitCountText, '2 of 3');

    assertThrows(function() {
      regExpSelector.regexp = '';
    });

    document.body.removeChild(div);
  });
});
