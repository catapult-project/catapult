/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {assert} from 'chai';
import {groupAlerts} from './group-alerts.js';

suite('group-alerts', function() {
  test('group_overlapping', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'bar',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'baz',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 1);
    assert.lengthOf(grouped[0], 2);
  });

  test('group_barely_overlapping', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'bar',
        startRevision: 0,
        endRevision: 1,
      },
      {
        suite: 'foo',
        measurement: 'baz',
        startRevision: 1,
        endRevision: 2,
      },
    ]);
    assert.lengthOf(grouped, 1);
    assert.lengthOf(grouped[0], 2);
  });

  test('some_overlapping', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'bar',
        startRevision: 0,
        endRevision: 1,
      },
      {
        suite: 'foo',
        measurement: 'baz',
        startRevision: 1,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'qux',
        startRevision: 2,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 2);
    assert.lengthOf(grouped[1], 1);
  });

  test('non_overlapping', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'bar',
        startRevision: 0,
        endRevision: 1,
      },
      {
        suite: 'foo',
        measurement: 'baz',
        startRevision: 2,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 1);
    assert.lengthOf(grouped[1], 1);
  });

  test('different_testsuite', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'baz',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'bar',
        measurement: 'qux',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 1);
    assert.lengthOf(grouped[1], 1);
  });

  test('same_measurement_name', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 1);
    assert.lengthOf(grouped[0], 2);
  });

  test('related', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:browser_process:reported_by_os:' +
        'gpu_memory:proportional_resident_size',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 1);
    assert.lengthOf(grouped[0], 2);
  });

  test('relatedAcrossTestSuites', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'bar',
        measurement: 'memory:chrome:browser_process:reported_by_os:' +
        'gpu_memory:proportional_resident_size',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 1);
    assert.lengthOf(grouped[0], 2);
  });

  test('unrelated', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_chrome:' +
        'shim_allocated_objects_size',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 1);
    assert.lengthOf(grouped[1], 1);
  });

  test('some_related', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_os:gpu_memory:' +
        'proportional_resident_size',
        startRevision: 0,
        endRevision: 1,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:browser_process:reported_by_os:' +
        'gpu_memory:proportional_resident_size',
        startRevision: 0,
        endRevision: 1,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_chrome:' +
        'shim_allocated_objects_size',
        startRevision: 0,
        endRevision: 1,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 2);
    assert.lengthOf(grouped[1], 1);
  });

  test('some_relatable', function() {
    const grouped = groupAlerts([
      {
        suite: 'foo',
        measurement: 'power',
        startRevision: 0,
        endRevision: 2,
      },
      {
        suite: 'foo',
        measurement: 'memory:chrome:all_processes:reported_by_chrome:' +
        'shim_allocated_objects_size',
        startRevision: 1,
        endRevision: 3,
      },
    ]);
    assert.lengthOf(grouped, 2);
    assert.lengthOf(grouped[0], 1);
    assert.lengthOf(grouped[1], 1);
  });
});
