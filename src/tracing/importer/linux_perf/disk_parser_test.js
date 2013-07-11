// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.disk_parser', function() {
  test('diskImport', function() {
    var lines = [
      // NB: spliced from different traces; mismatched timestamps don't matter
      'AsyncTask #2-18830 [000] ...1 154578.668286: ext4_sync_file_enter: ' +
          'dev 259,1 ino 81993 parent 81906 datasync 1',
      'mmcqd/0-81    [000] d..2 154578.668390: block_rq_issue: ' +
          '179,0 WS 0 () 3427120 + 16 [mmcqd/0]',
      'mmcqd/0-81    [000] d..2 154578.669181: block_rq_complete: ' +
          '179,0 WS () 3427120 + 16 [0]',
      'mmcqd/0-81    [001] d..2 154578.670853: block_rq_issue: ' +
          '179,0 FWS 0 () 18446744073709551615 + 0 [mmcqd/0]',
      'mmcqd/0-81    [001] d..2 154578.670869: block_rq_complete: ' +
          '179,0 FWS () 18446744073709551615 + 0 [0]',
      'AsyncTask #2-18830 [001] ...1 154578.670901: ext4_sync_file_exit: ' +
          'dev 259,1 ino 81993 ret 0',
      'mmcqd/0-81    [001] d..2 154578.877038: block_rq_issue: ' +
          '179,0 R 0 () 3255256 + 8 [mmcqd/0]',
      'mmcqd/0-81    [001] d..2 154578.877110: block_rq_issue: ' +
          '179,0 R 0 () 3255288 + 8 [mmcqd/0]',
      'mmcqd/0-81    [000] d..2 154578.877345: block_rq_complete: ' +
          '179,0 R () 3255256 + 8 [0]',
      'mmcqd/0-81    [000] d..2 154578.877466: block_rq_complete: ' +
          '179,0 R () 3255288 + 8 [0]'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var blockThread = undefined;
    var ext4Thread = undefined;
    m.getAllThreads().forEach(function(t) {
      switch (t.name) {
        case 'block:mmcqd/0':
          blockThread = t;
          break;
        case 'ext4:AsyncTask #2':
          ext4Thread = t;
          break;
        default:
          throw new unittest.TestError('Unexpected thread named ' + t.name);
      }
    });
    assertNotUndefined(blockThread);
    assertNotUndefined(ext4Thread);

    assertEquals(4, blockThread.asyncSliceGroup.length);

    var slice = blockThread.asyncSliceGroup.slices[0];
    assertEquals('block', slice.category);
    assertEquals('write sync', slice.title);
    assertEquals('179,0', slice.args.device);
    assertEquals(0, slice.args.error);
    assertEquals(16, slice.args.numSectors);
    assertEquals(3427120, slice.args.sector);

    assertEquals(1, ext4Thread.asyncSliceGroup.length);

    slice = ext4Thread.asyncSliceGroup.slices[0];
    assertEquals('ext4', slice.category);
    assertEquals('fdatasync', slice.title);
    assertEquals('259,1', slice.args.device);
    assertEquals(0, slice.args.error);
    assertEquals(81993, slice.args.inode);
  });
});
