// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview This file provides a JavaScript helper function that
 * determines whether service worker registration has completed.
 */
(function() {
  // Make executing this code idempotent.
  if (window.__telemetry_queryServiceWorkerState) {
    return;
  }

  // These variable is used for detecting and waiting service worker
  // registration.
  let isServiceWorkerRegistered = false;
  let isServiceWorkerReady = false;

  // Patch navigator.serviceWorker.register
  navigator.serviceWorker.originalRegister = navigator.serviceWorker.register;
  navigator.serviceWorker.register = (name, options = {}) => {
    isServiceWorkerRegistered = true;
    navigator.serviceWorker.originalRegister(name, options);
  };

  navigator.serviceWorker.ready.then(
      (registration) => { isServiceWorkerReady = true; });

  window.__telemetry_queryServiceWorkerState = () => {
    // These return string should exactly match strings used in
    // ServiceWorkerState, in web_contents.py
    if (!isServiceWorkerRegistered) {
      return isServiceWorkerReady ? 'unknown state' : 'not registered';
    }
    return isServiceWorkerReady ? 'activated' : 'installing';
  };
})();
