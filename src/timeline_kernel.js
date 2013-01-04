// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineProcess class.
 */
base.require('timeline_process_base');

base.exportTo('tracing', function() {

  /**
   * The TimelineKernel represents kernel-level objects in the
   * model.
   * @constructor
   */
  function TimelineKernel() {
    tracing.TimelineProcessBase.call(this);
  };

  /**
   * Comparison between kernels is pretty meaningless.
   */
  TimelineKernel.compare = function(x, y) {
    return 0;
  };

  TimelineKernel.prototype = {
    __proto__: tracing.TimelineProcessBase.prototype,

    compareTo: function(that) {
      return TimelineKernel.compare(this, that);
    },

    get userFriendlyName() {
      return 'kernel';
    },

    get userFriendlyDetails() {
      return 'kernel';
    }
  };

  return {
    TimelineKernel: TimelineKernel
  };
});
