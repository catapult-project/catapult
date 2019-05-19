/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import 'bower_components/webcomponentsjs/webcomponents-loader.js';
import {ElementBase, STORE} from './element-base.js';
import {RESET} from './simple-redux.js';
import {animationFrame, afterRender} from './utils.js';

Mocha.before(async function() {
  const deps = document.createElement('link');
  deps.rel = 'import';
  deps.href = '/dashboard/spa/dependencies.html';
  document.head.appendChild(deps);
  while (!window.tr || !tr.b || !tr.b.Timing || !tr.b.Timing.mark || !tr.v ||
          !tr.v.Histogram || !tr.v.HistogramSet) {
    await animationFrame();
  }
});

Mocha.beforeEach(async function() {
  window.AUTH_CLIENT_ID = '';
  window.location.hash = '';
  STORE.dispatch(RESET);
  await afterRender();
});

const testsContext = require.context('.', true, /\.test\.js$/);
testsContext.keys().forEach(testsContext);
