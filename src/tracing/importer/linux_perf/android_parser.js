// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses trace_marker events that were inserted in the trace by
 * userland.
 */
base.require('tracing.importer.linux_perf.parser');
base.exportTo('tracing.importer.linux_perf', function() {

  var Parser = tracing.importer.linux_perf.Parser;

  /**
   * Parses linux trace mark events that were inserted in the trace by userland.
   * @constructor
   */
  function AndroidParser(importer) {
    Parser.call(this, importer);

    importer.registerEventHandler('tracing_mark_write:android',
        AndroidParser.prototype.traceMarkWriteAndroidEvent.bind(this));
    importer.registerEventHandler('0:android',
        AndroidParser.prototype.traceMarkWriteAndroidEvent.bind(this));

    this.model_ = importer.model_;
    this.ppids_ = {};
  }

  function parseArgs(argsString) {
    var args = {};
    if (argsString) {
      var argsArray = argsString.split(';');
      for (var i = 0; i < argsArray.length; ++i) {
        var parts = argsArray[i].split('=');
        if (parts[0])
          args[parts.shift()] = parts.join('=');
      }
    }
    return args;
  }

  AndroidParser.prototype = {
    __proto__: Parser.prototype,

    traceMarkWriteAndroidEvent: function(eventName, cpuNumber, pid, ts,
                                  eventBase) {
      var eventData = eventBase.details.split('|');
      switch (eventData[0]) {
        case 'B':
          var ppid = parseInt(eventData[1]);
          var category = eventData[4];
          var title = eventData[2];
          var thread = this.model_.getOrCreateProcess(ppid)
            .getOrCreateThread(pid);
          thread.name = eventBase.threadName;
          if (!thread.isTimestampValidForBeginOrEnd(ts)) {
            this.model_.importErrors.push(
                'Timestamps are moving backward.');
            return false;
          }

          this.ppids_[pid] = ppid;
          thread.beginSlice(category, title, ts, parseArgs(eventData[3]));

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

          var args = parseArgs(eventData[3]);
          for (var arg in args) {
            if (slice.args[arg] !== undefined) {
              this.model_.importErrors.push(
                  'Both the B and E events of ' + slice.title +
                  'provided values for argument ' + arg + '. ' +
                  'The value of the E event will be used.');
            }
            slice.args[arg] = args[arg];
          }

          break;
        case 'C':
          var ppid = parseInt(eventData[1]);
          var name = eventData[2];
          var value = parseInt(eventData[3]);
          var category = eventData[4];

          var ctr = this.model_.getOrCreateProcess(ppid)
              .getOrCreateCounter(category, name);
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
    }
  };

  Parser.registerSubtype(AndroidParser);

  return {
    AndroidParser: AndroidParser
  };
});
