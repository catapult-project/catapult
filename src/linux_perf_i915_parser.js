// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses i915 driver events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux i915 trace events.
   * @constructor
   */
  function LinuxPerfI915Parser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('i915_gem_object_create',
        LinuxPerfI915Parser.prototype.gemObjectCreateEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_bind',
        LinuxPerfI915Parser.prototype.gemObjectBindEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_unbind',
        LinuxPerfI915Parser.prototype.gemObjectBindEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_change_domain',
        LinuxPerfI915Parser.prototype.gemObjectChangeDomainEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_pread',
        LinuxPerfI915Parser.prototype.gemObjectPreadWriteEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_pwrite',
        LinuxPerfI915Parser.prototype.gemObjectPreadWriteEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_fault',
        LinuxPerfI915Parser.prototype.gemObjectFaultEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_clflush',
        // NB: reuse destroy handler
        LinuxPerfI915Parser.prototype.gemObjectDestroyEvent.bind(this));
    importer.registerEventHandler('i915_gem_object_destroy',
        LinuxPerfI915Parser.prototype.gemObjectDestroyEvent.bind(this));
    importer.registerEventHandler('i915_gem_ring_dispatch',
        LinuxPerfI915Parser.prototype.gemRingDispatchEvent.bind(this));
    importer.registerEventHandler('i915_gem_ring_flush',
        LinuxPerfI915Parser.prototype.gemRingFlushEvent.bind(this));
    importer.registerEventHandler('i915_gem_request',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_request_add',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_request_complete',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_request_retire',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_request_wait_begin',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_request_wait_end',
        LinuxPerfI915Parser.prototype.gemRequestEvent.bind(this));
    importer.registerEventHandler('i915_gem_ring_wait_begin',
        LinuxPerfI915Parser.prototype.gemRingWaitEvent.bind(this));
    importer.registerEventHandler('i915_gem_ring_wait_end',
        LinuxPerfI915Parser.prototype.gemRingWaitEvent.bind(this));
    importer.registerEventHandler('i915_reg_rw',
        LinuxPerfI915Parser.prototype.regRWEvent.bind(this));
    importer.registerEventHandler('i915_flip_request',
        LinuxPerfI915Parser.prototype.flipEvent.bind(this));
    importer.registerEventHandler('i915_flip_complete',
        LinuxPerfI915Parser.prototype.flipEvent.bind(this));
  }

  LinuxPerfI915Parser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    i915FlipOpenSlice: function(ts, obj, plane) {
      // use i915_flip_obj_plane?
      var kthread = this.importer.getOrCreatePseudoThread('i915_flip');
      kthread.openSliceTS = ts;
      kthread.openSlice = 'flip:' + obj + '/' + plane;
    },

    i915FlipCloseSlice: function(ts, args) {
      var kthread = this.importer.getOrCreatePseudoThread('i915_flip');
      if (kthread.openSlice) {
        var slice = new tracing.TimelineSlice('', kthread.openSlice,
            tracing.getStringColorId(kthread.openSlice),
            kthread.openSliceTS,
            args,
            ts - kthread.openSliceTS);

        kthread.thread.pushSlice(slice);
      }
      kthread.openSlice = undefined;
    },

    i915GemObjectSlice: function(ts, eventName, obj, args) {
      var kthread = this.importer.getOrCreatePseudoThread('i915_gem');
      kthread.openSlice = eventName + ':' + obj;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    i915GemRingSlice: function(ts, eventName, dev, ring, args) {
      var kthread = this.importer.getOrCreatePseudoThread('i915_gem_ring');
      kthread.openSlice = eventName + ':' + dev + '.' + ring;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    i915RegSlice: function(ts, eventName, reg, args) {
      var kthread = this.importer.getOrCreatePseudoThread('i915_reg');
      kthread.openSlice = eventName + ':' + reg;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    /**
     * Parses i915 driver events and sets up state in the importer.
     */
    gemObjectCreateEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /obj=(\w+), size=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      var size = parseInt(event[2]);
      this.i915GemObjectSlice(ts, eventName, obj,
          {
            obj: obj,
            size: size
          });
      return true;
    },

    gemObjectBindEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      // TODO(sleffler) mappable
      var event = /obj=(\w+), offset=(\w+), size=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      var offset = event[2];
      var size = parseInt(event[3]);
      this.i915ObjectGemSlice(ts, eventName + ':' + obj,
          {
            obj: obj,
            offset: offset,
            size: size
          });
      return true;
    },

    gemObjectChangeDomainEvent: function(eventName, cpuNumber, pid, ts,
                                         eventBase) {
      var event = /obj=(\w+), read=(\w+=>\w+), write=(\w+=>\w+)/
          .exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      var read = event[2];
      var write = event[3];
      this.i915GemObjectSlice(ts, eventName, obj,
          {
            obj: obj,
            read: read,
            write: write
          });
      return true;
    },

    gemObjectPreadWriteEvent: function(eventName, cpuNumber, pid, ts,
                                       eventBase) {
      var event = /obj=(\w+), offset=(\d+), len=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      var offset = parseInt(event[2]);
      var len = parseInt(event[3]);
      this.i915GemObjectSlice(ts, eventName, obj,
          {
            obj: obj,
            offset: offset,
            len: len
          });
      return true;
    },

    gemObjectFaultEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      // TODO(sleffler) writable
      var event = /obj=(\w+), (\w+) index=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      var type = event[2];
      var index = parseInt(event[3]);
      this.i915GemObjectSlice(ts, eventName, obj,
          {
            obj: obj,
            type: type,
            index: index
          });
      return true;
    },

    gemObjectDestroyEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /obj=(\w+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var obj = event[1];
      this.i915GemObjectSlice(ts, eventName, obj,
          {
            obj: obj
          });
      return true;
    },

    gemRingDispatchEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /dev=(\d+), ring=(\d+), seqno=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var dev = parseInt(event[1]);
      var ring = parseInt(event[2]);
      var seqno = parseInt(event[3]);
      this.i915GemRingSlice(ts, eventName, dev, ring,
          {
            dev: dev,
            ring: ring,
            seqno: seqno
          });
      return true;
    },

    gemRingFlushEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /dev=(\d+), ring=(\w+), invalidate=(\w+), flush=(\w+)/
          .exec(eventBase[5]);
      if (!event)
        return false;

      var dev = parseInt(event[1]);
      var ring = parseInt(event[2]);
      var invalidate = event[3];
      var flush = event[4];
      this.i915GemRingSlice(ts, eventName, dev, ring,
          {
            dev: dev,
            ring: ring,
            invalidate: invalidate,
            flush: flush
          });
      return true;
    },

    gemRequestEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /dev=(\d+), ring=(\d+), seqno=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var dev = parseInt(event[1]);
      var ring = parseInt(event[2]);
      var seqno = parseInt(event[3]);
      this.i915GemRingSlice(ts, eventName, dev, ring,
          {
            dev: dev,
            ring: ring,
            seqno: seqno
          });
      return true;
    },

    gemRingWaitEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /dev=(\d+), ring=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var dev = parseInt(event[1]);
      var ring = parseInt(event[2]);
      this.i915GemRingSlice(ts, eventName, dev, ring,
          {
            dev: dev,
            ring: ring
          });
      return true;
    },

    regRWEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /(\w+) reg=(\w+), len=(\d+), val=(\(\w+, \w+\))/
          .exec(eventBase[5]);
      if (!event)
        return false;

      var rw = event[1];
      var reg = event[2];
      var len = event[3];
      var data = event[3];
      this.i915RegSlice(ts, rw, reg,
          {
            rw: rw,
            reg: reg,
            len: len,
            data: data
          });
      return true;
    },

    flipEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /plane=(\d+), obj=(\w+)/.exec(eventBase[5]);
      if (!event)
        return false;

      var plane = parseInt(event[1]);
      var obj = event[2];
      if (eventName == 'i915_flip_request')
        this.i915FlipOpenSlice(ts, obj, plane);
      else
        this.i915FlipCloseSlice(ts,
            {
              obj: obj,
              plane: plane
            });
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfI915Parser);

  return {
    LinuxPerfI915Parser: LinuxPerfI915Parser
  };
});
