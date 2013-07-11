// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.tracks.process_track_base');

base.exportTo('tracing.tracks', function() {
  var ProcessTrackBase = tracing.tracks.ProcessTrackBase;

  /**
   * @constructor
   */
  var ProcessTrack = ui.define('process-track', ProcessTrackBase);

  ProcessTrack.prototype = {
    __proto__: ProcessTrackBase.prototype,

    decorate: function(viewport) {
      tracing.tracks.ProcessTrackBase.prototype.decorate.call(this, viewport);
    },

    // Process maps to processBase because we derive from ProcessTrackBase.
    set process(process) {
      this.processBase = process;
    },

    get process() {
      return this.processBase;
    }
  };


  return {
    ProcessTrack: ProcessTrack
  };
});
