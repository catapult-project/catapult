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
        assertEquals(0, m.importErrors.length);

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
        assertEquals(0, m.importErrors.length);

        var c0 = m.kernel.cpus[0];
        assertEquals(0, c0.slices.length);
        assertEquals(3, c0.counters['INT Frequency'].series[0].samples.length);
        assertEquals(1, c0.counters['MIF Frequency'].series[0].samples.length);
      });
    });
