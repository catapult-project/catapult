// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.tile');
base.require('cc.tile_view');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');
base.require('cc.layer_tree_host_impl_test_data');

base.unittest.testSuite('cc.tile', function() {
  test('basic', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = base.dictionaryValues(m.processes)[0];
    var instance = p.objects.getAllInstancesNamed('cc::Tile')[0];
    var snapshot = instance.snapshots[0];

    assertTrue(snapshot instanceof cc.TileSnapshot);
  });
});
