/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

METRICS.frontendVersion = 2;

window.IS_DEBUG = location.hostname === 'localhost';
const PRODUCTION = 'v2spa-dot-chromeperf.appspot.com';
window.IS_PRODUCTION = location.hostname === PRODUCTION;

window.AUTH_CLIENT_ID = !IS_PRODUCTION ? '' :
  '62121018386-rhk28ad5lbqheinh05fgau3shotl2t6c.apps.googleusercontent.com';

if ('serviceWorker' in navigator && !IS_DEBUG) {
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

// These packages use base imports so they can be webpacked but not dynamically
// loaded in tests.
import '@polymer/app-route/app-location.js';
import '@polymer/app-route/app-route.js';
import '@polymer/iron-collapse/iron-collapse.js';
import '@polymer/iron-icon/iron-icon.js';
import '@polymer/iron-iconset-svg/iron-iconset-svg.js';

import './chromeperf-app.js';
