// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.picture');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');
base.require('cc.picture_view_test_data');

base.unittest.testSuite('cc.picture', function() {
  test('basic', function() {
    var m = new tracing.TraceModel([g_picture_trace]);
    var p = base.dictionaryValues(m.processes)[0];
    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    assertTrue(snapshot instanceof cc.PictureSnapshot);
    instance.wasDeleted(150);
  });

  test('getOps', function() {
    var picture = new cc.PictureSnapshot({id: '31415'}, 10, {
      'params': {
        'opaque_rect': [-15, -15, 0, 0],
        'layer_rect': [-15, -15, 46, 833]
      },
      'skp64': 'DAAAAHYEAADzAQAABwAAAAFkYWVy8AAAAAgAAB4DAAAADAAAIAAAgD8AAIA/CAAAHgMAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADoAAAACAAAHgMAAAAMAAAjAAAAAAAAAAAMAAAjAAAAAAAAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADkAAAAGAAAFQEAAAAAAAAAAAAAAADAjkQAgPlDGAAAFQIAAAAAAAAAAAAAAADAjkQAgPlDCAAAHgMAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADgAAAAGAAAFQMAAAAAAKBAAACgQAAAgEIAAIBCBAAAHAQAABwEAAAcBAAAHHRjYWYBAAAADVNrU3JjWGZlcm1vZGVjZnB0AAAAAHlhcmGgAAAAIHRucAMAAAAAAEBBAACAPwAAAAAAAIA/AAAAAAAAgEAAAP//ADABAAAAAAAAAEBBAACAPwAAAAAAAIA/AAAAAAAAgED/////AjABAAAAAAAAAAAAAAAAAAEAAAAEAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQEEAAIA/AAAAAAAAgD8AAAAAAACAQP8AAP8AMAEAAAAAACBmb2U=' // @suppress longLineCheck
    });
    picture.preInitialize();
    picture.initialize();

    var ops = picture.getOps();
    if (!ops)
      return;
    assertEquals(22, ops.length);

    var op0 = ops[0];
    assertEquals('Save', op0.cmd_string);
    assertTrue(op0.info instanceof Array);
  });
});
