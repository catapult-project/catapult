// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.cpufreq_parser',
                        function() {
      test('cpuFreqTargetImport', function() {
        var lines = [
          '<idle>-0     [000] ..s3  1043.718825: cpufreq_interactive_target: ' +
              'cpu=0 load=2 cur=2000000 targ=300000\n',
          '<idle>-0     [000] ..s3  1043.718825: cpufreq_interactive_target: ' +
              'cpu=0 load=12 cur=1000000 actual=1000000 targ=200000\n'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(0, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(2, thread.sliceGroup.slices[0].args['load']);
        assertEquals(2000000, thread.sliceGroup.slices[0].args['cur']);
        assertEquals(300000, thread.sliceGroup.slices[0].args['targ']);

        assertEquals(0, thread.sliceGroup.slices[1].args['cpu']);
        assertEquals(12, thread.sliceGroup.slices[1].args['load']);
        assertEquals(1000000, thread.sliceGroup.slices[1].args['cur']);
        assertEquals(1000000, thread.sliceGroup.slices[1].args['actual']);
        assertEquals(200000, thread.sliceGroup.slices[1].args['targ']);
      });

      test('cpuFreqNotYetImport', function() {
        var lines = [
          '<idle>-0     [001] ..s3  1043.718832: cpufreq_interactive_notyet: ' +
              'cpu=1 load=10 cur=700000 targ=200000\n',
          '<idle>-0     [001] ..s3  1043.718832: cpufreq_interactive_notyet: ' +
              'cpu=1 load=10 cur=700000 actual=1000000 targ=200000\n'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(1, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(10, thread.sliceGroup.slices[0].args['load']);
        assertEquals(700000, thread.sliceGroup.slices[0].args['cur']);
        assertEquals(200000, thread.sliceGroup.slices[0].args['targ']);

        assertEquals(1, thread.sliceGroup.slices[1].args['cpu']);
        assertEquals(10, thread.sliceGroup.slices[1].args['load']);
        assertEquals(700000, thread.sliceGroup.slices[1].args['cur']);
        assertEquals(1000000, thread.sliceGroup.slices[1].args['actual']);
        assertEquals(200000, thread.sliceGroup.slices[1].args['targ']);
      });

      test('cpuFreqSetSpeedImport', function() {
        var lines = [
          'cfinteractive-23    [001] ...1  1043.719688: ' +
              'cpufreq_interactive_setspeed: cpu=0 targ=200000 actual=700000\n'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(0, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(200000, thread.sliceGroup.slices[0].args['targ']);
        assertEquals(700000, thread.sliceGroup.slices[0].args['actual']);
      });

      test('cpuFreqAlreadyImport', function() {
        var lines = [
          '<idle>-0     [000] ..s3  1043.738822: cpufreq_interactive_already: cpu=0 load=18 cur=200000 actual=700000 targ=200000\n' // @suppress longLineCheck
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(0, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(18, thread.sliceGroup.slices[0].args['load']);
        assertEquals(200000, thread.sliceGroup.slices[0].args['cur']);
        assertEquals(700000, thread.sliceGroup.slices[0].args['actual']);
        assertEquals(200000, thread.sliceGroup.slices[0].args['targ']);
      });

      test('cpuFreqBoostImport', function() {
        var lines = [
          'InputDispatcher-465   [001] ...1  1044.213948: ' +
              'cpufreq_interactive_boost: pulse\n'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals('pulse', thread.sliceGroup.slices[0].args['type']);
      });

      test('cpuFreqUnBoostImport', function() {
        var lines = [
          'InputDispatcher-465   [001] ...1  1044.213948: ' +
              'cpufreq_interactive_unboost: pulse\n'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals('pulse', thread.sliceGroup.slices[0].args['type']);
      });

      test('cpuFreqUpImport', function() {
        var lines = [
          'kinteractive-69    [003] .... 414324.164432: ' +
              'cpufreq_interactive_up: cpu=1 targ=1400000 actual=800000'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(1, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(1400000, thread.sliceGroup.slices[0].args['targ']);
        assertEquals(800000, thread.sliceGroup.slices[0].args['actual']);
      });

      test('cpuFreqDownImport', function() {
        var lines = [
          'kinteractive-69    [003] .... 414365.834193: ' +
              'cpufreq_interactive_down: cpu=3 targ=800000 actual=1000000'
        ];
        var m = new tracing.TraceModel(lines.join('\n'), false);
        assertEquals(0, m.importErrors.length);

        var threads = m.getAllThreads();
        assertEquals(1, threads.length);

        var thread = threads[0];
        assertEquals(3, thread.sliceGroup.slices[0].args['cpu']);
        assertEquals(800000, thread.sliceGroup.slices[0].args['targ']);
        assertEquals(1000000, thread.sliceGroup.slices[0].args['actual']);
      });
    });
