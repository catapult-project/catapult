// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Implements a WebSocket client that receives
 * a stream of slices from a server.
 *
 */

tvcm.require('tvcm.events');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.trace_model.slice');

tvcm.exportTo('tracing.importer', function() {

  var STATE_PAUSED = 0x1;
  var STATE_CAPTURING = 0x2;

  /**
   * Converts a stream of trace data from a websocket into a model.
   *
   * Events consumed by this importer have the following JSON structure:
   *
   * {
   *   'cmd': 'commandName',
   *   ... command specific data
   * }
   *
   * The importer understands 2 commands:
   *      'ptd' (Process Thread Data)
   *      'pcd' (Process Counter Data)
   *
   * The command specific data is as follows:
   *
   * {
   *   'pid': 'Remote Process Id',
   *   'td': {
   *                  'n': 'Thread Name Here',
   *                  's: [ {
   *                              'l': 'Slice Label',
   *                              's': startTime,
   *                              'e': endTime
   *                              }, ... ]
   *         }
   * }
   *
   * {
   *  'pid' 'Remote Process Id',
   *  'cd': {
   *      'n': 'Counter Name',
   *      'sn': ['Series Name',...]
   *      'sc': [seriesColor, ...]
   *      'c': [
   *            {
   *              't': timestamp,
   *              'v': [value0, value1, ...]
   *            },
   *            ....
   *           ]
   *       }
   * }
   * @param {Model} model that will be updated
   * when events are received.
   * @constructor
   */
  function TimelineStreamImporter(model) {
    var self = this;
    this.model_ = model;
    this.connection_ = undefined;
    this.state_ = STATE_CAPTURING;
    this.connectionOpenHandler_ =
        this.connectionOpenHandler_.bind(this);
    this.connectionCloseHandler_ =
        this.connectionCloseHandler_.bind(this);
    this.connectionErrorHandler_ =
        this.connectionErrorHandler_.bind(this);
    this.connectionMessageHandler_ =
        this.connectionMessageHandler_.bind(this);
  }

  TimelineStreamImporter.prototype = {
    __proto__: tvcm.EventTarget.prototype,

    cleanup_: function() {
      if (!this.connection_)
        return;
      this.connection_.removeEventListener('open',
          this.connectionOpenHandler_);
      this.connection_.removeEventListener('close',
          this.connectionCloseHandler_);
      this.connection_.removeEventListener('error',
          this.connectionErrorHandler_);
      this.connection_.removeEventListener('message',
          this.connectionMessageHandler_);
    },

    connectionOpenHandler_: function() {
      this.dispatchEvent({'type': 'connect'});
    },

    connectionCloseHandler_: function() {
      this.dispatchEvent({'type': 'disconnect'});
      this.cleanup_();
    },

    connectionErrorHandler_: function() {
      this.dispatchEvent({'type': 'connectionerror'});
      this.cleanup_();
    },

    connectionMessageHandler_: function(event) {
      var packet = JSON.parse(event.data);
      var command = packet['cmd'];
      var pid = packet['pid'];
      var modelDirty = false;
      if (command == 'ptd') {
        var process = this.model_.getOrCreateProcess(pid);
        var threadData = packet['td'];
        var threadName = threadData['n'];
        var threadSlices = threadData['s'];
        var thread = process.getOrCreateThread(threadName);
        for (var s = 0; s < threadSlices.length; s++) {
          var slice = threadSlices[s];
          thread.sliceGroup.pushSlice(new tracing.trace_model.ThreadSlice(
              'streamed',
              slice['l'],
              0,
              slice['s'],
              {},
              slice['e'] - slice['s']));
        }
        modelDirty = true;
      } else if (command == 'pcd') {
        var process = this.model_.getOrCreateProcess(pid);
        var counterData = packet['cd'];
        var counterName = counterData['n'];
        var counterSeriesNames = counterData['sn'];
        var counterSeriesColors = counterData['sc'];
        var counterValues = counterData['c'];
        var counter = process.getOrCreateCounter('streamed', counterName);
        if (counterSeriesNames.length != counterSeriesColors.length) {
          this.model_.importWarning({
            type: 'parse_error',
            message: 'Streamed counter name length does not match' +
                ' counter color length' + counterSeriesNames.length +
                ' vs ' + counterSeriesColors.length
          });
          return;
        }
        if (counter.series.length === 0) {
          for (var i = 0; i < counterSeriesNames.length; ++i) {
            counter.addSeries(new tracing.trace_model.CounterSeries(
                counterSeriesNames[i], counterSeriesColors[i]));
          }
        } else {
          if (counter.series.length != counterSeriesNames.length) {
            this.model_.importWarning({
              type: 'parse_error',
              message: 'Streamed counter ' + counterName +
                  ' changed number of seriesNames'
            });
            return;
          } else {
            for (var i = 0; i < counter.series.length; i++) {
              var oldSeriesName = counter.series[i].name;
              var newSeriesName = counterSeriesNames[i];

              if (oldSeriesName != newSeriesName) {
                this.model_.importWarning({
                  type: 'parse_error',
                  message: 'Streamed counter ' + counterName +
                      ' series name changed from ' + oldSeriesName + ' to ' +
                      newSeriesName
                });
                return;
              }
            }
          }
        }
        for (var c = 0; c < counterValues.length; c++) {
          var count = counterValues[c];
          var ts = count['t'];
          var values = count['v'];
          for (var i = 0; i < values.length; ++i) {
            counter.series[i].addCounterSample(ts, values[i]);
          }
        }
        modelDirty = true;
      }
      if (modelDirty == true) {
        this.model_.updateBounds();
        this.dispatchEvent({'type': 'modelchange',
          'model': this.model_});
      }
    },

    get connected() {
      if (this.connection_ !== undefined &&
          this.connection_.readyState == WebSocket.OPEN) {
        return true;
      }
      return false;
    },

    get paused() {
      return this.state_ == STATE_PAUSED;
    },

    /**
     * Connects the stream to a websocket.
     * @param {WebSocket} wsConnection The websocket to use for the stream.
     */
    connect: function(wsConnection) {
      this.connection_ = wsConnection;
      this.connection_.addEventListener('open',
          this.connectionOpenHandler_);
      this.connection_.addEventListener('close',
          this.connectionCloseHandler_);
      this.connection_.addEventListener('error',
          this.connectionErrorHandler_);
      this.connection_.addEventListener('message',
          this.connectionMessageHandler_);
    },

    pause: function() {
      if (this.state_ == STATE_PAUSED)
        throw new Error('Already paused.');
      if (!this.connection_)
        throw new Error('Not connected.');
      this.connection_.send(JSON.stringify({'cmd': 'pause'}));
      this.state_ = STATE_PAUSED;
    },

    resume: function() {
      if (this.state_ == STATE_CAPTURING)
        throw new Error('Already capturing.');
      if (!this.connection_)
        throw new Error('Not connected.');
      this.connection_.send(JSON.stringify({'cmd': 'resume'}));
      this.state_ = STATE_CAPTURING;
    }
  };

  return {
    TimelineStreamImporter: TimelineStreamImporter
  };
});
