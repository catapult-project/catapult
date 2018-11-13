/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

tr.exportTo('window', () => {
  const DEBUG = location.hostname === 'localhost';
  const PRODUCTION = 'v2spa-dot-chromeperf.appspot.com';
  const IS_PRODUCTION = location.hostname === PRODUCTION;

  // Register the Service Worker when in production. Service Workers are not
  // helpful in development mode because all backend responses are being mocked.
  if ('serviceWorker' in navigator && !DEBUG) {
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

  return {
    IS_PRODUCTION,
  };
});
