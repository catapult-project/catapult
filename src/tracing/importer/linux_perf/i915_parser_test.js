// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.i915_parser', function() {
  test('i915Import', function() {
    var lines = [
      // NB: spliced from different traces; mismatched timestamps don't matter
      '          chrome-1223  [000]  2784.773556: i915_gem_object_pwrite: ' +
                 'obj=ffff88013f13fc00, offset=0, len=2984',
      '          chrome-1539  [000] 18420.677750: ' +
                 'i915_gem_object_change_domain: ' +
                 'obj=ffff8800a88d1400, read=44=>40, write=00=>40',
      '          chrome-1539  [000] 18420.677759: i915_gem_object_fault: ' +
                 'obj=ffff8800a88d1400, GTT index=0 , writable',
      '               X-964   [000]  2784.774864: i915_flip_request: ' +
                 'plane=0, obj=ffff88013f0b9a00',
      '          <idle>-0     [000]  2784.788644: i915_flip_complete: ' +
                 'plane=0, obj=ffff88013f0b9a00',
      '          chrome-1539  [001] 18420.681687: i915_gem_request_retire: ' +
                 'dev=0, ring=1, seqno=1178152',
      '          chrome-1539  [000] 18422.955688: i915_gem_request_add: ' +
                 'dev=0, ring=1, seqno=1178364',
      '             cat-21833 [000] 18422.956832: i915_gem_request_complete: ' +
                 'dev=0, ring=1, seqno=1178364',
      '             X-1012  [001] 18420.682511: i915_gem_request_wait_begin: ' +
                 'dev=0, ring=4, seqno=1178156',
      '               X-1012  [000] 18422.765707: i915_gem_request_wait_end: ' +
                 'dev=0, ring=4, seqno=1178359',
      '          chrome-1539  [000] 18422.955655: i915_gem_ring_flush: ' +
                 'dev=0, ring=1, invalidate=001e, flush=0040',
      '          chrome-1539  [000] 18422.955660: i915_gem_ring_dispatch: ' +
                 'dev=0, ring=1, seqno=1178364',
      '          chrome-1539  [000] 18420.677772: i915_reg_rw: ' +
                 'write reg=0x100030, len=8, val=(0xfca9001, 0xfce8007)'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var i915GemThread = undefined;
    var i915FlipThread = undefined;
    var i915GemRingThread = undefined;
    var i915RegThread = undefined;
    m.getAllThreads().forEach(function(t) {
      switch (t.name) {
        case 'i915_gem':
          i915GemThread = t;
          break;
        case 'i915_flip':
          i915FlipThread = t;
          break;
        case 'i915_gem_ring':
          i915GemRingThread = t;
          break;
        case 'i915_reg':
          i915RegThread = t;
          break;
        default:
          throw new unittest.TestError('Unexpected thread named ' + t.name);
      }
    });
    assertNotUndefined(i915GemThread);
    assertNotUndefined(i915FlipThread);
    assertNotUndefined(i915GemRingThread);
    assertNotUndefined(i915RegThread);

    assertEquals(3, i915GemThread.sliceGroup.length);

    assertEquals(1, i915FlipThread.sliceGroup.length);

    assertAlmostEquals(2784.774864 * 1000.0,
        i915FlipThread.sliceGroup.slices[0].start);
    assertAlmostEquals((2784.788644 - 2784.774864) * 1000.0,
        i915FlipThread.sliceGroup.slices[0].duration);

    assertEquals(7, i915GemRingThread.sliceGroup.length);
    assertEquals(1, i915RegThread.sliceGroup.length);
  });
});
