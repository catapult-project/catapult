// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses trace_marker events that were inserted in the trace by
 * userland.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux trace mark events that were inserted in the trace by userland.
   * @constructor
   */
  function LinuxPerfAndroidParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('tracing_mark_write:android',
        LinuxPerfAndroidParser.prototype.traceMarkWriteAndroidEvent.bind(this));
    importer.registerEventHandler('0:android',
        LinuxPerfAndroidParser.prototype.traceMarkWriteAndroidEvent.bind(this));

    this.model_ = importer.model_;
    this.ppids_ = {};
  }

  LinuxPerfAndroidParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    traceMarkWriteAndroidEvent: function(eventName, cpuNumber, pid, ts,
                                  eventBase, threadName) {
      var eventData = eventBase[2].split('|');
      switch (eventData[0]) {
        case 'B':
          var ppid = parseInt(eventData[1]);
          var name = eventData[2];
          var thread = this.model_.getOrCreateProcess(ppid)
            .getOrCreateThread(pid);
          thread.name = threadName;
          if (!thread.isTimestampValidForBeginOrEnd(ts)) {
            this.model_.importErrors.push(
                'Timestamps are moving backward.');
            return false;
          }

          this.ppids_[pid] = ppid;
          thread.beginSlice(null, name, ts, {});

          break;
        case 'E':
          var ppid = this.ppids_[pid];
          if (ppid === undefined) {
            // Silently ignore unmatched E events.
            break;
          }

          var thread = this.model_.getOrCreateProcess(ppid)
            .getOrCreateThread(pid);
          if (!thread.openSliceCount) {
            // Silently ignore unmatched E events.
            break;
          }

          var slice = thread.endSlice(ts);

          // TODO(jgennis): add real support for arguments
          args = {};
          for (var arg in args) {
            if (slice.args[arg] !== undefined) {
              this.model_.importErrors.push(
                  'Both the B and E events of ' + slice.name +
                  'provided values for argument ' + arg + '. ' +
                  'The value of the E event will be used.');
            }
            slice.args[arg] = event.args[arg];
          }

          break;
        case 'C':
          var ppid = parseInt(eventData[1]);
          var name = eventData[2];
          var value = parseInt(eventData[3]);

          var ctr = this.model_.getOrCreateProcess(ppid)
              .getOrCreateCounter(null, name);
          // Initialize the counter's series fields if needed.
          if (ctr.numSeries == 0) {
            ctr.seriesNames.push('value');
            ctr.seriesColors.push(
                tracing.getStringColorId(ctr.name + '.' + 'value'));
          }

          // Add the sample value.
          ctr.timestamps.push(ts);
          ctr.samples.push(value);

          break;
        default:
          return false;
      }

      return true;
    },
  };

  LinuxPerfParser.registerSubtype(LinuxPerfAndroidParser);

  return {
    LinuxPerfAndroidParser: LinuxPerfAndroidParser
  };
});
