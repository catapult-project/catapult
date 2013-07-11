// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.drm_parser', function() {
  test('drmImport', function() {
    var lines = [
      ' chrome-2465  [000]    71.653157: drm_vblank_event: crtc=0, seq=4233',
      ' <idle>-0     [000]    71.669851: drm_vblank_event: crtc=0, seq=4234'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var threads = m.getAllThreads();
    assertEquals(1, threads.length);

    var vblankThread = threads[0];
    assertEquals('drm_vblank', vblankThread.name);
    assertEquals(2, vblankThread.sliceGroup.length);
  });
});
