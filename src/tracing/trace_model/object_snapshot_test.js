// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.object_instance');
base.require('tracing.trace_model.object_snapshot');

base.unittest.testSuite('tracing.trace_model.object_snapshot', function() {
  test('snapshotTypeRegistry', function() {
    function MySnapshot() {
      tracing.trace_model.ObjectSnapshot.apply(this, arguments);
      this.myFoo = this.args.foo;
    }

    MySnapshot.prototype = {
      __proto__: tracing.trace_model.ObjectSnapshot.prototype
    };

    var instance = new tracing.trace_model.ObjectInstance(
        {}, '0x1000', 'cat', 'MySnapshot', 10);
    try {
      tracing.trace_model.ObjectSnapshot.register('MySnapshot', MySnapshot);
      var snapshot = instance.addSnapshot(15, {foo: 'bar'});
      assertTrue(snapshot instanceof MySnapshot);
      assertEquals('bar', snapshot.myFoo);
    } finally {
      tracing.trace_model.ObjectSnapshot.unregister('MySnapshot');
    }
  });
});
