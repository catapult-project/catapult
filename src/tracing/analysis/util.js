// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Helper functions for use in selection_analysis files.
 */

base.exportTo('tracing.analysis', function() {

  function tsRound(ts) {
    return Math.round(ts * 1000.0) / 1000.0;
  }

  return {
    tsRound: tsRound
  };

});
