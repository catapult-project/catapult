/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import * as TASK_QUEUE from './task-queue.js';
import {assert} from 'chai';
import {timeout} from './utils.js';

suite('TASK_QUEUE', function() {
  test('flush', async() => {
    let complete = false;
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    await TASK_QUEUE.flush();
    assert.isTrue(complete);
  });

  test('scheduleFlush', async() => {
    let complete = false;
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    TASK_QUEUE.scheduleFlush(1);
    await timeout(10);
    assert.isTrue(complete);
  });

  test('cancel scheduled flush', async() => {
    let complete = false;
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    TASK_QUEUE.scheduleFlush(1);
    TASK_QUEUE.cancelFlush();
    await timeout(10);
    assert.isFalse(complete);
  });

  test('cancel running flush', async() => {
    let complete = false;
    TASK_QUEUE.schedule(async() => {
      await timeout(5);
    });
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    const flushPromise = TASK_QUEUE.flush();
    TASK_QUEUE.cancelFlush();
    await flushPromise;
    assert.isFalse(complete);
  });

  test('flush while flushing', async() => {
    let complete = false;
    TASK_QUEUE.schedule(async() => {
      await timeout(5);
    });
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    const flushPromise = TASK_QUEUE.flush();
    // The second flush() should return early.
    await TASK_QUEUE.flush();
    assert.isFalse(complete);

    // The first flush() should complete all tasks.
    await flushPromise;
    assert.isTrue(complete);
  });

  test('ignore errors', async() => {
    let complete = false;
    TASK_QUEUE.schedule(function() {
      throw new Error('intentional error');
    });
    TASK_QUEUE.schedule(async() => {
      complete = true;
    });
    await TASK_QUEUE.flush();
    assert.isTrue(complete);
  });
});
