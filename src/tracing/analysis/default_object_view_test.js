// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.default_object_view');
base.require('tracing.selection');
base.require('tracing.trace_model.object_instance');

base.unittest.testSuite('tracing.analysis.default_object_view', function() {
  test('instantiate_snapshotView', function() {
    var i10 = new tracing.trace_model.ObjectInstance(
        {}, '0x1000', 'cat', 'name', 10);
    var s10 = i10.addSnapshot(10, {foo: 1});
    i10.updateBounds();

    var view = new tracing.analysis.DefaultObjectSnapshotView();
    view.objectSnapshot = s10;
    this.addHTMLOutput(view);
  });

  test('instantiate_instanceView', function() {
    var i10 = new tracing.trace_model.ObjectInstance(
        {}, '0x1000', 'cat', 'name', 10);
    var s10 = i10.addSnapshot(10, {foo: 1});
    var s20 = i10.addSnapshot(20, {foo: 2});
    i10.updateBounds();

    var view = new tracing.analysis.DefaultObjectInstanceView();
    view.objectInstance = i10;
    this.addHTMLOutput(view);
  });
});
