// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.overlay');

base.unittest.testSuite('ui.overlay', function() {
  test('instantiate', function() {
    var dlg = new ui.Overlay();
    dlg.classList.add('example-overlay');
    dlg.innerHTML = '<div class="header">ExampleOverlay</div>hello';

    var btn = document.createElement('button');
    btn.innerText = 'Launch Overlay';
    btn.addEventListener('click', function(e) {
      dlg.visible = true;
      e.stopPropagation();
    });

    this.addHTMLOutput(btn);
  });

  test('instantiate_disableUserClose', function() {
    var dlg = new ui.Overlay();
    dlg.classList.add('example-overlay');
    dlg.userCanClose = false;
    dlg.innerHTML = '<div class="header">ExampleOverlay</div>';

    var btn = document.createElement('button');
    btn.innerText = 'close';
    btn.addEventListener('click', function(e) {
      dlg.visible = false;
    });
    dlg.appendChild(btn);

    btn = document.createElement('button');
    btn.innerText = 'Launch Overlay';
    btn.addEventListener('click', function(e) {
      dlg.visible = true;
      e.stopPropagation();
    });

    this.addHTMLOutput(btn);
  });
});
