// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.exynos_parser',
                        function() {
      test('exynosImport', function() {
        var lines = [
          ' X-945   [001] ....   113.995549: exynos_flip_request: pipe=0',
          ' X-945   [001] ....   113.995561: exynos_flip_complete: pipe=0'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertFalse(m.hasImportWarnings);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var gfxFlipThread = threads[0];
        assertEquals('exynos_flip', gfxFlipThread.name);
        assertEquals(1, gfxFlipThread.sliceGroup.length);
      });

      test('exynosBusfreqImport', function() {
        var lines = [
          '     kworker/1:0-4177  [001] ....  2803.129806: ' +
              'exynos_busfreq_target_int: frequency=200000',
          '     kworker/1:0-4177  [001] ....  2803.229207: ' +
              'exynos_busfreq_target_int: frequency=267000',
          '     kworker/1:0-4177  [001] ....  2803.329031: ' +
              'exynos_busfreq_target_int: frequency=160000',
          '     kworker/1:0-4177  [001] ....  2805.729039: ' +
              'exynos_busfreq_target_mif: frequency=200000'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertFalse(m.hasImportWarnings);

        var c0 = m.kernel.cpus[0];
        assertEquals(0, c0.slices.length);
        assertEquals(3, c0.counters['INT Frequency'].series[0].samples.length);
        assertEquals(1, c0.counters['MIF Frequency'].series[0].samples.length);
      });

      test('exynosPageFlipSlowRequestImport', function() {
        var lines = [
          '          <idle>-0     [000] d.h. 1000.000000: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_kds',
          ' Chrome_IOThread-21603 [000] d.h. 1000.000001: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_apply',
          '     kworker/0:1-25931 [000] .... 1000.000002: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_flip',
          '     kworker/0:1-25931 [000] .... 1000.000003: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=flipped',
          '          <idle>-0     [000] d.h. 1000.000004: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_kds',
          ' Chrome_IOThread-21603 [000] d.h. 1000.000005: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_apply',
          '     kworker/0:1-25931 [000] .... 1000.000006: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_flip',
          '     kworker/0:1-25931 [000] .... 1000.000007: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=flipped'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertFalse(m.hasImportWarnings);

        var threads = m.getAllThreads();
        // there are 2 threads:
        //   (1) "exynos_flip_state (pipe:0, fb:25)"
        //   (2) "exynos_flip_state (pipe:0, fb:26)"
        assertEquals(2, threads.length);

        // in the test data, event of fb=26 occurs first, so it's thread[0]
        var gfxFbId26Thread = threads[0]; // thread where fb == 26
        var gfxFbId25Thread = threads[1]; // thread where fb == 25
        assertEquals('exynos_flip_state (pipe:0, fb:25)', gfxFbId25Thread.name);
        assertEquals('exynos_flip_state (pipe:0, fb:26)', gfxFbId26Thread.name);
        // Every state (except for 'flipped') will start a new slice.
        // The last event will not be closed, so it's not a slice
        assertEquals(3, gfxFbId25Thread.sliceGroup.length);
        assertEquals(3, gfxFbId26Thread.sliceGroup.length);
      });

      test('exynosPageFlipFastRequestImport', function() {
        var lines = [
          '          <idle>-0     [000] d.h. 1000.000000: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_kds',
          ' Chrome_IOThread-21603 [000] d.h. 1000.000001: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_kds',
          '               X-21385 [000] .... 1000.000002: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_apply',
          '     kworker/0:1-25931 [000] .... 1000.000003: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_flip',
          '               X-21385 [001] .... 1000.000004: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_apply',
          '     kworker/0:1-25931 [000] .... 1000.000005: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=flipped',
          '          <idle>-0     [000] d.h. 1000.000006: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_kds',
          '               X-21385 [000] .... 1000.000007: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_flip',
          '     kworker/0:1-25931 [000] .... 1000.000008: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=flipped',
          '     kworker/0:1-25931 [000] .... 1000.000009: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_kds',
          ' Chrome_IOThread-21603 [000] d.h. 1000.000010: ' +
              'exynos_page_flip_state: pipe=0, fb=25, state=wait_apply',
          '          <idle>-0     [000] d.h. 1000.000011: ' +
              'exynos_page_flip_state: pipe=0, fb=26, state=wait_apply'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertFalse(m.hasImportWarnings);

        var threads = m.getAllThreads();
        // there are 2 threads:
        //   (1) "exynos_flip_state (pipe:0, fb:25)"
        //   (2) "exynos_flip_state (pipe:0, fb:26)"
        assertEquals(2, threads.length);

        // in the test data, event of fb=26 occurs first, so it's thread[0]
        var gfxFbId26Thread = threads[0]; // thread where fb == 26
        var gfxFbId25Thread = threads[1]; // thread where fb == 25
        assertEquals('exynos_flip_state (pipe:0, fb:25)', gfxFbId25Thread.name);
        assertEquals('exynos_flip_state (pipe:0, fb:26)', gfxFbId26Thread.name);
        // Every state (except for 'flipped') will start a new slice.
        // The last event will not be closed, so it's not a slice
        assertEquals(4, gfxFbId25Thread.sliceGroup.length);
        assertEquals(4, gfxFbId26Thread.sliceGroup.length);
      });
    });
