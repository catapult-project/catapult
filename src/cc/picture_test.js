// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('cc.picture');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');
base.require('cc.picture_view_test_data');

'use strict';

base.unittest.testSuite('cc.picture', function() {
  test('basic', function() {
    var m = new tracing.TraceModel([g_picture_trace]);
    var p = base.dictionaryValues(m.processes)[0];
    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    assertTrue(snapshot instanceof cc.PictureSnapshot);
    instance.wasDeleted(150);
  });
});
