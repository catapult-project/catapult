// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.overlay');

base.unittest.testSuite('ui.overlay', function() {
  test('showHideUnparented', function() {
    var overlay = new ui.Overlay();
    overlay.innerHTML =
        '<h3>Hello</h3>B1:<button>foo</button></p>B2:<button>blah</button>';
    overlay.visible = true;
    assertNotEquals(overlay.parentNode, null);

    overlay.visible = false;
    assertEquals(overlay.parentNode, null);
  });

  test('showHideParented', function() {
    var overlay = new ui.Overlay();
    overlay.innerHTML =
        '<h3>Hello</h3>B1:<button>foo</button></p>B2:<button>blah</button>';

    document.body.appendChild(overlay);
    overlay.visible = true;
    assertNotEquals(overlay.parentNode, null);

    overlay.visible = false;
    assertEquals(overlay.parentNode, document.body);
    document.body.removeChild(overlay);
  });
});
