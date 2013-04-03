// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('test_utils');
base.require('model');
base.require('selection');
base.require('tracks.thread_track');
base.require('tracks.counter_track');

/**
 * @fileoverview Helper functions for use in analysis tests.
 */

base.exportTo('tracing.analysis.test', function() {

    var newSliceNamed = test_utils.newSliceNamed;
    var newSliceCategory = test_utils.newSliceCategory;

    function createReferenceData(withCategory) {
      var model = new tracing.Model();
      var p1 = model.getOrCreateProcess(1);
      var t1 = p1.getOrCreateThread(1);
      if (withCategory)
        t1.pushSlice(newSliceCategory('foo', 'b', 0, 0.002));
      else
        t1.pushSlice(newSliceNamed('b', 0, 0.002));
      t1.pushSlice(newSliceNamed('b', 0, 0.002));
      t1.pushSlice(newSliceNamed('c', 0, 0.002));
      t1.pushSlice(newSliceNamed('c', .01, 0.003));
      t1.pushSlice(newSliceNamed('c', .01, 0.001));
      t1.pushSlice(newSliceNamed('c', .02, 0.004));
      t1.pushSlice(newSliceNamed('d', 0, 0.002));
      t1.pushSlice(newSliceNamed('d', .01, 0.003));
      t1.pushSlice(newSliceNamed('d', .01, 0.001));
      t1.pushSlice(newSliceNamed('d', .02, 0.004));
      t1.pushSlice(newSliceNamed('e', 0, 0.002));
      t1.pushSlice(newSliceNamed('e', .01, 0.003));
      t1.pushSlice(newSliceNamed('e', .01, 0.001));
      t1.pushSlice(newSliceNamed('e', .02, 0.004));
      t1.pushSlice(newSliceNamed('f', 0, 0.002));
      t1.pushSlice(newSliceNamed('Slice with a really, really long name.',
                                  0, 0.005));

      t1.slices.push(new tracing.model.Slice('category', 'D', 0, 1.15,
                                             {src_file: 'Arg D src_file',
                                              src_func: 'Arg D src_func'}, .5));
      t1.slices.push(new tracing.model.Slice('cat', 'E', 0, 1,
                                             {src_file: 'Arg E src_file',
                                              src_func: 'Arg E src_func'}, .4));
      t1.slices.push(new tracing.model.Slice('cat', 'F', 0, 1,
                                             {src_file: '0',
                                              src_func: 'false'}, .4));

      var ctr1 = p1.getOrCreateCounter('foo', 'ctr1');
      ctr1.seriesNames.push('bytesallocated', 'bytesfree');
      ctr1.seriesColors.push(0, 1);
      ctr1.timestamps.push(0, 10, 20);
      ctr1.samples.push(0, 25, 10, 15, 20, 5);

      var ctr2 = p1.getOrCreateCounter('foo', 'ctr2');
      ctr2.seriesNames.push('bytesallocated', 'bytesfree');
      ctr2.seriesColors.push(0, 1);
      ctr2.timestamps.push(0, 10, 20);
      ctr2.samples.push(0, 25, 10, 15, 20, 5);

      var t1track = new tracing.tracks.ThreadTrack();
      t1track.thread = t1;
      var ctr1track = new tracing.tracks.CounterTrack();
      ctr1track.counter = ctr1;

      var ctr2track = new tracing.tracks.CounterTrack();
      ctr2track.counter = ctr2;

      t1track.selectByTitle = function(title, selection) {
        t1track.addAllObjectsMatchingFilterToSelection(
            new tracing.TitleFilter(title), selection);
      }

      return {model: model,
              t1track: t1track,
              ctr1track: ctr1track,
              ctr2track: ctr2track};
    }

    return {
      createReferenceData: createReferenceData
    };
});

