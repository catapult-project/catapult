// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('cc', function() {
  var constants = {};
  constants.ACTIVE_TREE = 0;
  constants.PENDING_TREE = 1;

  constants.HIGH_PRIORITY_BIN = 0;
  constants.LOW_PRIORITY_BIN = 1;

  return {
    constants: constants
  };
});
