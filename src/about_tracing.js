// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('about_tracing.profiling_view');
base.requireStylesheet('about_tracing');

base.exportTo('about_tracing', function() {
  window.tracingController = undefined;
  window.profilingView = undefined;  // Made global for debugging purposes only.

  document.addEventListener('DOMContentLoaded', function() {
    window.tracingController = new about_tracing.TracingController(
        chrome.send.bind(chrome));

    window.profilingView = new about_tracing.ProfilingView();
    document.body.appendChild(profilingView);
    window.profilingView.tracingController = window.tracingController;
  });

  return {};
});
