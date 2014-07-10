// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.sampling_summary_side_panel');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.test_utils');

tvcm.unittest.testSuite('tracing.sampling_summary_side_panel_test', function() {
  var StackFrame = tracing.trace_model.StackFrame;
  var Sample = tracing.trace_model.Sample;

  var newSliceNamed = tracing.test_utils.newSliceNamed;

  function createSelection() {
    var selection = new tracing.Selection();
    var model = new tracing.TraceModel();
    var thread = model.getOrCreateProcess(1).getOrCreateThread(2);
    thread.name = 'The Thread';

    var fA = new StackFrame(undefined, 1, 'Chrome', 'a', 7);
    var fAB = new StackFrame(fA, 2, 'Chrome', 'b', 7);
    var fABC = new StackFrame(fAB, 3, 'Chrome', 'c', 7);
    var fAD = new StackFrame(fA, 4, 'GPU Driver', 'd', 7);

    selection.push(new Sample(undefined, thread, 'cycles',
                              10, fABC, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              20, fAB, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              25, fAB, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              30, fAB, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              35, fAD, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              35, fAD, 5));
    selection.push(new Sample(undefined, thread, 'cycles',
                              40, fAD, 5));
    selection.push(new Sample(undefined, thread, 'page_misses',
                              35, fAD, 7));
    selection.push(new Sample(undefined, thread, 'page_misses',
                              40, fAD, 9));
    return selection;
  }

  test('createSunburstDataBasic', function() {
    var s = createSelection();

    var expect = {
      name: '<All Threads>',
      category: 'root',
      children: [
        {
          name: 'Thread 2: The Thread',
          category: 'Thread',
          children: [
            {
              category: 'Chrome',
              name: 'Chrome',
              children: [
                {
                  category: 'Chrome',
                  name: 'a',
                  children: [
                    {
                      category: 'Chrome',
                      name: 'b',
                      children: [
                        {
                          category: 'Chrome',
                          name: 'c',
                          size: 10
                        },
                        {
                          name: '<self>',
                          category: 'Chrome',
                          size: 30
                        }
                      ]
                    },
                    {
                      category: 'GPU Driver',
                      name: 'd',
                      size: 20
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    };

    var sunburstData = tracing.createSunburstData(s, 'cycles');
    assertEquals(JSON.stringify(expect), JSON.stringify(sunburstData));
  });

  test('processOnlySamples', function() {
    var selection = new tracing.Selection();
    var model = new tracing.TraceModel();
    var thread = model.getOrCreateProcess(1).getOrCreateThread(2);
    thread.name = 'The Thread';

    var fA = new StackFrame(undefined, 1, 'Chrome', 'a', 7);
    var fAB = new StackFrame(fA, 2, 'Chrome', 'b', 7);
    var fABC = new StackFrame(fAB, 3, 'Chrome', 'c', 7);
    var fAD = new StackFrame(fA, 4, 'GPU Driver', 'd', 7);

    selection.push(new Sample(undefined, thread, 'cycles',
                              10, fABC, 10));
    selection.push(new Sample(undefined, thread, 'cycles',
                              20, fAB, 10));
    selection.push(new Sample(undefined, thread, 'page_misses',
                              40, fAD, 9));
    var expect = {
      name: '<All Threads>',
      category: 'root',
      children: [
        {
          name: 'Thread 2: The Thread',
          category: 'Thread',
          children: [
            {
              category: 'Chrome',
              name: 'Chrome',
              children: [
                {
                  category: 'Chrome',
                  name: 'a',
                  children: [
                    {
                      category: 'GPU Driver',
                      name: 'd',
                      size: 9
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    };

    // Along with the samples, push some slices too.
    // The panel should completely ignore these.
    selection.push(newSliceNamed('a', 1, 2));
    selection.push(newSliceNamed('f', 9, 7));

    var sunburstData = tracing.createSunburstData(selection, 'page_misses');
    assertEquals(JSON.stringify(expect), JSON.stringify(sunburstData));
  });

  test('createSunburstDataSampleType', function() {
    var s = createSelection();

    var expect = {
      name: '<All Threads>',
      category: 'root',
      children: [
        {
          name: 'Thread 2: The Thread',
          category: 'Thread',
          children: [
            {
              category: 'Chrome',
              name: 'Chrome',
              children: [
                {
                  category: 'Chrome',
                  name: 'a',
                  children: [
                    {
                      category: 'GPU Driver',
                      name: 'd',
                      size: 16
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    };

    var sunburstData = tracing.createSunburstData(s, 'page_misses');
    assertEquals(JSON.stringify(expect), JSON.stringify(sunburstData));
  });

  test('instantiate', function() {
    var s = createSelection();

    var panel = new tracing.SamplingSummarySidePanel();
    this.addHTMLOutput(panel);
    panel.style.border = '1px solid black';
    panel.selection = s;
  });
});
