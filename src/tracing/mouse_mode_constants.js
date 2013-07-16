// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('tracing', function() {

  var mouseModeConstants = {};
  mouseModeConstants.MOUSE_MODE_SELECTION = 1;
  mouseModeConstants.MOUSE_MODE_PANSCAN = 2;
  mouseModeConstants.MOUSE_MODE_ZOOM = 3;

  return {
    mouseModeConstants: mouseModeConstants
  };
});
