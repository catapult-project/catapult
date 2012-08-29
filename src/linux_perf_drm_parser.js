// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses drm driver events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux drm trace events.
   * @constructor
   */
  function LinuxPerfDrmParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('drm_vblank_event',
        LinuxPerfDrmParser.prototype.vblankEvent.bind(this));
  }

  LinuxPerfDrmParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    drmVblankSlice: function(ts, eventName, args) {
      var kthread = this.importer.getOrCreatePseudoThread('drm_vblank');
      kthread.openSlice = eventName;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    /**
     * Parses drm driver events and sets up state in the importer.
     */
    vblankEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /crtc=(\d+), seq=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var crtc = parseInt(event[1]);
      var seq = parseInt(event[2]);
      this.drmVblankSlice(ts, 'vblank:' + crtc,
          {
            crtc: crtc,
            seq: seq
          });
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfDrmParser);

  return {
    LinuxPerfDrmParser: LinuxPerfDrmParser
  };
});
