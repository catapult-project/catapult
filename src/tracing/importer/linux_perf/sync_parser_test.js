// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.sync_parser', function() { // @suppress longLineCheck
  test('syncEventImport', function() {
    var lines = [
      's3c-fb-92            (     0) [000] ...1  7206.550061: sync_timeline: name=s3c-fb value=7094', // @suppress longLineCheck
      'TimedEventQueue-2700 (     0) [001] ...1  7206.569027: sync_wait: begin name=SurfaceView:6 state=1', // @suppress longLineCheck
      'TimedEventQueue-2700 (     0) [001] ...1  7206.569038: sync_pt: name=malitl_124_0x40b6406c value=7289', // @suppress longLineCheck
      'TimedEventQueue-2700 (     0) [001] ...1  7206.569056: sync_pt: name=exynos-gsc.0-src value=25', // @suppress longLineCheck
      'TimedEventQueue-2700 (     0) [001] ...1  7206.569068: sync_wait: end name=SurfaceView:6 state=1', // @suppress longLineCheck
      'irq/128-s5p-mfc-62   (     0) [000] d..3  7206.572402: sync_timeline: name=vb2 value=37', // @suppress longLineCheck
      'irq/128-s5p-mfc-62   (     0) [000] d..3  7206.572475: sync_timeline: name=vb2 value=33', // @suppress longLineCheck
      'SurfaceFlinger-225   (     0) [001] ...1  7206.584769: sync_timeline: name=malitl_124_0x40b6406c value=7290', // @suppress longLineCheck
      'kworker/u:5-2269     (     0) [000] ...1  7206.586745: sync_wait: begin name=display state=1', // @suppress longLineCheck
      'kworker/u:5-2269     (     0) [000] ...1  7206.586750: sync_pt: name=s3c-fb value=7093', // @suppress longLineCheck
      'kworker/u:5-2269     (     0) [000] ...1  7206.586760: sync_wait: end name=display state=1', // @suppress longLineCheck
      's3c-fb-92            (     0) [000] ...1  7206.587193: sync_wait: begin name=vb2 state=0', // @suppress longLineCheck
      's3c-fb-92            (     0) [000] ...1  7206.587198: sync_pt: name=exynos-gsc.0-dst value=27', // @suppress longLineCheck
      '<idle>-0             (     0) [000] d.h4  7206.591133: sync_timeline: name=exynos-gsc.0-src value=27', // @suppress longLineCheck
      '<idle>-0             (     0) [000] d.h4  7206.591152: sync_timeline: name=exynos-gsc.0-dst value=27', // @suppress longLineCheck
      's3c-fb-92            (     0) [000] ...1  7206.591244: sync_wait: end name=vb2 state=1' // @suppress longLineCheck
    ];

    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var threads = m.getAllThreads();
    assertEquals(4, threads.length);

    var threads = m.findAllThreadsNamed('s3c-fb');
    assertEquals(1, threads.length);
    assertEquals(1, threads[0].sliceGroup.length);

    var threads = m.findAllThreadsNamed('kworker/u:5');
    assertEquals(1, threads.length);
    assertEquals(1, threads[0].sliceGroup.length);
    assertEquals('fence_wait("display")',
                 threads[0].sliceGroup.slices[0].title);
  });
});
