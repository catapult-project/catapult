/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

METRICS.frontendVersion = 2;

import {isDebug} from './utils.js';

if ('serviceWorker' in navigator && !isDebug()) {
  document.addEventListener('DOMContentLoaded', async() => {
    await navigator.serviceWorker.register(
        'service-worker.js?' + VULCANIZED_TIMESTAMP.getTime());

    if (navigator.serviceWorker.controller === null) {
      // Technically, everything would work without the service worker, but it
      // would be unbearably slow. Reload so that the service worker can
      // finish installing.
      location.reload();
    }
  });
}

import './chromeperf-app.js';
