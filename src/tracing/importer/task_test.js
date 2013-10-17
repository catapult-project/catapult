// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.importer.task');

base.unittest.testSuite('tracing.importer.task', function() {
  var Task = tracing.importer.Task;

  test('basicAllStepsPass', function() {
    var results = [];

    var startingTask = new Task(function(task) {
      results.push('a');
      task.subTask(function() {
        results.push('a/1');
      }, this);
      task.subTask(function() {
        results.push('a/2');
      }, this);
    }, this);
    startingTask.after(function() {
      results.push('b');
    }, this).after(function() {
      results.push('c');
    }, this);

    Task.RunSynchronously(startingTask);
    assertArrayEquals(['a', 'a/1', 'a/2', 'b', 'c'],
                      results);
  });

  test('basicAllStepsPassAsync', function() {
    var results = [];

    var startingTask = new Task(function(task) {
      results.push('a');
      task.subTask(function() {
        results.push('a/1');
      }, this);
      task.subTask(function() {
        results.push('a/2');
      }, this);
    }, this);
    startingTask.after(function() {
      results.push('b');
    }, this).after(function() {
      results.push('c');
    }, this);

    var promise = Task.RunWhenIdle(startingTask);
    promise.then(function() {
      assertArrayEquals(['a', 'a/1', 'a/2', 'b', 'c'],
                        results);
    });
    return promise;
  });

  test('taskThatThrowsShouldRejectItsPromise', function() {
    var startingTask = new Task(function(task) {
      throw new Errror('Expected error');
    }, this);

    var taskPromise = Task.RunWhenIdle(startingTask);

    return new Promise(function(resolver) {
      taskPromise.then(function() {
        resolver.reject(new Error('Should have thrown'));
      }, function(err) {
        resolver.resolve();
      });
    });
  });

});
