/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

const PAUSED = 'paused';
const RUNNING = 'running';
const PAUSING = 'pausing';

let STATE = PAUSED;
let TIMEOUT_ID;
const QUEUE = [];

export function schedule(task) {
  QUEUE.push(task);
}

export function scheduleFlush(delayMs = 1000) {
  TIMEOUT_ID = setTimeout(flush, delayMs);
}

export function cancelFlush() {
  if (TIMEOUT_ID) clearTimeout(TIMEOUT_ID);
  if (STATE === RUNNING) STATE = PAUSING;
}

export async function flush() {
  // This async method could potentially take several seconds, during which
  // time the caller could schedule another task. In order to prevent
  // deadlocks, there should only be a single flush() running at once.
  if (STATE !== PAUSED) return;
  STATE = RUNNING;

  // eslint-disable-next-line no-unmodified-loop-condition
  while (QUEUE.length && (STATE === RUNNING)) {
    const task = QUEUE.shift();
    try {
      await task();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn(err);
    }
  }

  STATE = PAUSED;
}
