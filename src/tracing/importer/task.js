// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.raf');
base.require('base.promise');

base.exportTo('tracing.importer', function() {
  /**
   * @constructor
   */
  function Task(runCb, thisArg) {
    if (thisArg === undefined)
      throw new Error('Almost certainly, you meant to pass a thisarg.');
    this.runCb_ = runCb;
    this.thisArg_ = thisArg;
    this.afterTask_ = undefined;
    this.subTasks_ = [];
  }

  Task.prototype = {
    pushSubTask: function(cb, thisArg) {
      if (cb instanceof Task)
        this.subTasks_.push(cb);
      else
        this.subTasks_.push(new Task(cb, thisArg));
      return this.subTasks_[this.subTasks_.length - 1];
    },

    run: function() {
      this.runCb_.call(this.thisArg_, this);
      var subTasks = this.subTasks_;
      this.subTasks_ = undefined; // Prevent more subTasks from being posted.

      if (!subTasks.length) {
        return this.afterTask_;
      } else {
        for (var i = 1; i < subTasks.length; i++)
          subTasks[i - 1].afterTask_ = subTasks[i];
        subTasks[subTasks.length - 1].afterTask_ = this.afterTask_;
        return subTasks[0];
      }
    },

    after: function(cb, thisArg) {
      if (this.afterTask_)
        throw new Error('Has an after task already');
      if (cb instanceof Task)
        this.afterTask_ = cb;
      else
        this.afterTask_ = new Task(cb, thisArg);
      return this.afterTask_;
    }
  };

  Task.RunSynchronously = function(task) {
    var curTask = task;
    while (curTask)
      curTask = curTask.run();
  }

  /**
   * Runs a task using raf.requestIdleCallback, returning
   * a promise for its completion.
   */
  Task.RunWhenIdle = function(task) {
    return new base.Promise(function(resolver) {
      var curTask = task;
      function runAnother() {
        curTask = curTask.run();

        if (curTask) {
          base.requestIdleCallback(runAnother);
          return;
        }

        resolver.resolve();
      }
      base.requestIdleCallback(runAnother);
    });
  }

  return {
    Task: Task
  };
});
