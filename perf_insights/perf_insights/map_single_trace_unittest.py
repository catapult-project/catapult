# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import unittest

from perf_insights import in_memory_trace_handle
from perf_insights import map_single_trace
from perf_insights import function_handle
from perf_insights import results as results_module
from perf_insights import value as value_module


def _Handle(filename):
  module = function_handle.ModuleToLoad(filename=filename)
  return function_handle.FunctionHandle(modules_to_load=[module],
                                        function_name='MyMapFunction')


class MapSingleTraceTests(unittest.TestCase):

  def testPassingMapScript(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      pi.FunctionRegistry.register(
          function MyMapFunction(results, canonical_url, model) {
            results.addValue(new pi.v.DictValue(
              canonical_url,
              'result', {
                numProcesses: model.getAllProcesses().length
              }));
          });
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertFalse(results.failure_values)
    v = results.FindValueNamed('result')
    self.assertEquals(v['numProcesses'], 1)

  def testTraceDidntImport(self):
    trace_string = 'This is intentionally not a trace-formatted string.'
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', trace_string)

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      pi.FunctionRegistry.register(
          function MyMapFunction(results, canonical_url, model) {
          });
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, map_single_trace.TraceImportErrorValue)

  def testMapFunctionThatThrows(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      pi.FunctionRegistry.register(
          function MyMapFunction(results, canonical_url, model) {
            throw new Error('Expected error');
          });
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, map_single_trace.MapFunctionErrorValue)

  def testMapperWithLoadeError(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      throw new Error('Expected load error');
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, map_single_trace.FunctionLoadingErrorValue)

  def testNoMapper(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, map_single_trace.FunctionNotDefinedErrorValue)

  def testMapperDoesntAddValues(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      pi.FunctionRegistry.register(
          function MyMapFunction(results, canonical_url, model) {
      });
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, map_single_trace.NoResultsAddedErrorValue)

  def testMapperSkips(self):
    events = [
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'a', 'cat': 'c',
       'ts': 0, 'dur': 10, 'args': {}},
      {'pid': 1, 'tid': 2, 'ph': 'X', 'name': 'b', 'cat': 'c',
       'ts': 3, 'dur': 5, 'args': {}}
    ]
    trace_handle = in_memory_trace_handle.InMemoryTraceHandle(
        '/a.json', json.dumps(events))

    results = results_module.Results()
    with map_single_trace.TemporaryMapScript("""
      pi.FunctionRegistry.register(
          function MyMapFunction(results, canonical_url, model) {
            results.addValue(new pi.v.SkipValue(
                canonical_url, 'SkippedFieldName',
                {description: 'SkippedReason'}));

      });
    """) as map_script:
      map_single_trace.MapSingleTrace(results, trace_handle,
                                      _Handle(map_script.filename))

    self.assertEquals(len(results.all_values), 1)
    v = results.all_values[0]
    self.assertIsInstance(v, value_module.SkipValue)
    self.assertEquals(v.name, 'SkippedFieldName')
    self.assertEquals(v.description, 'SkippedReason')
