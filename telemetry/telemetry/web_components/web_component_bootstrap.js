// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

var g_results;
document.addEventListener('DOMContentLoaded', function() {
  var componentDataScript = document.querySelector(
      '#telemetry-web-component-data');
  var data;
  try {
    data = JSON.parse(componentDataScript.textContent);
  } catch (e) {
    tvcm.showPanic('Could not load data', e.stack || e);
  }
  g_results = new $js_class_name;
  g_results.$data_binding_property = data;
  document.body.appendChild(g_results);
});
