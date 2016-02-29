#!/usr/bin/env python

# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import unittest

from systrace import systrace
from systrace.agents import atrace_agent

DEVICE_SERIAL = 'AG8404EC0444AGC'
ATRACE_ARGS = ['atrace', '-z', '-t', '10', '-b', '4096']
CATEGORIES = ['sched', 'gfx', 'view', 'wm']
ADB_SHELL = ['adb', '-s', DEVICE_SERIAL, 'shell']

SYSTRACE_CMD = ['./systrace.py', '--time', '10', '-o', 'out.html', '-e',
                DEVICE_SERIAL] + CATEGORIES
TRACE_CMD = (ADB_SHELL + ATRACE_ARGS + CATEGORIES)

SYSTRACE_LIST_CATEGORIES_CMD = ['./systrace.py', '-e', DEVICE_SERIAL, '-l']
TRACE_LIST_CATEGORIES_CMD = (ADB_SHELL + ['atrace', '--list_categories'])

LEGACY_ATRACE_ARGS = ['atrace', '-z', '-t', '10', '-b', '4096', '-s']
LEGACY_TRACE_CMD = (ADB_SHELL + LEGACY_ATRACE_ARGS)

STOP_FIX_UPS = ['atrace', '--no-fix-threads', '--no-fix-tgids']


SYSTRACE_BOOT_CMD = (['./systrace.py', '--boot', '-e', DEVICE_SERIAL] +
                     CATEGORIES)
TRACE_BOOT_CMD = (ADB_SHELL +
                  ['atrace', '--async_stop', '&&', 'setprop',
                   'persist.debug.atrace.boottrace', '0', '&&',
                   'rm', '/data/misc/boottrace/categories'])

TEST_DIR = os.path.join(os.path.dirname(__file__), os.pardir, 'test_data')
ATRACE_DATA = os.path.join(TEST_DIR, 'atrace_data')
ATRACE_DATA_RAW = os.path.join(TEST_DIR, 'atrace_data_raw')
ATRACE_DATA_RAW_FROM_FILE = os.path.join(TEST_DIR, 'atrace_data_raw_from_file')
ATRACE_DATA_STRIPPED = os.path.join(TEST_DIR, 'atrace_data_stripped')
ATRACE_DATA_THREAD_FIXED = os.path.join(TEST_DIR, 'atrace_data_thread_fixed')
ATRACE_DATA_WITH_THREAD_LIST = os.path.join(TEST_DIR,
                                            'atrace_data_with_thread_list')
ATRACE_THREAD_NAMES = os.path.join(TEST_DIR, 'atrace_thread_names')
ATRACE_THREAD_LIST = os.path.join(TEST_DIR, 'atrace_ps_dump')
ATRACE_EXTRACTED_THREADS = os.path.join(TEST_DIR, 'atrace_extracted_threads')
ATRACE_PROCFS_DUMP = os.path.join(TEST_DIR, 'atrace_procfs_dump')
ATRACE_EXTRACTED_TGIDS = os.path.join(TEST_DIR, 'atrace_extracted_tgids')
ATRACE_MISSING_TGIDS = os.path.join(TEST_DIR, 'atrace_missing_tgids')
ATRACE_FIXED_TGIDS = os.path.join(TEST_DIR, 'atrace_fixed_tgids')


class AtraceAgentTest(unittest.TestCase):

  def test_construct_trace_command(self):
    options, categories = systrace.parse_options(SYSTRACE_CMD)
    agent = atrace_agent.AtraceAgent(options, categories)
    tracer_args = agent._construct_trace_command()
    self.assertEqual(' '.join(TRACE_CMD), ' '.join(tracer_args))
    self.assertEqual(True, agent.expect_trace())

  def test_extract_thread_list(self):
    with contextlib.nested(open(ATRACE_EXTRACTED_THREADS, 'r'),
                           open(ATRACE_THREAD_LIST)) as (f1, f2):

      atrace_result = f1.read()
      ps_dump = f2.read()

      thread_names = atrace_agent.extract_thread_list(ps_dump)
      self.assertEqual(atrace_result, str(thread_names))

  def test_strip_and_decompress_trace(self):
    with contextlib.nested(open(ATRACE_DATA_RAW, 'r'),
                           open(ATRACE_DATA_STRIPPED, 'r')) as (f1, f2):
      atrace_data_raw = f1.read()
      atrace_data_stripped = f2.read()

      trace_data = atrace_agent.strip_and_decompress_trace(atrace_data_raw)
      self.assertEqual(atrace_data_stripped, trace_data)

  def test_fix_thread_names(self):
    with contextlib.nested(
        open(ATRACE_DATA_STRIPPED, 'r'),
        open(ATRACE_THREAD_NAMES, 'r'),
        open(ATRACE_DATA_THREAD_FIXED, 'r')) as (f1, f2, f3):
      atrace_data_stripped = f1.read()
      atrace_thread_names = f2.read()
      atrace_data_thread_fixed = f3.read()
      thread_names = eval(atrace_thread_names)

      trace_data = atrace_agent.fix_thread_names(
          atrace_data_stripped, thread_names)
      self.assertEqual(atrace_data_thread_fixed, trace_data)

  def test_preprocess_trace_data(self):
    with contextlib.nested(open(ATRACE_DATA_STRIPPED, 'r'),
                           open(ATRACE_DATA_RAW, 'r')) as (f1, f2):
      atrace_data = f1.read()
      atrace_data_raw = f2.read()

      options, categories = systrace.parse_options(STOP_FIX_UPS)
      agent = atrace_agent.AtraceAgent(options, categories)
      trace_data = agent._preprocess_trace_data(atrace_data_raw)

      self.assertEqual(atrace_data, trace_data)

  def test_list_categories(self):
    options, categories = systrace.parse_options(SYSTRACE_LIST_CATEGORIES_CMD)
    agent = atrace_agent.AtraceAgent(options, categories)
    tracer_args = agent._construct_trace_command()
    self.assertEqual(' '.join(TRACE_LIST_CATEGORIES_CMD), ' '.join(tracer_args))
    self.assertEqual(False, agent.expect_trace())

  def test_construct_trace_from_file_command(self):
    options, categories = systrace.parse_options(['systrace.py',
        '--from-file', ATRACE_DATA_RAW_FROM_FILE])
    agent = atrace_agent.try_create_agent(options, categories)
    tracer_args = agent._construct_trace_command()
    self.assertEqual(' '.join(['cat', ATRACE_DATA_RAW_FROM_FILE]),
            ' '.join(tracer_args))
    self.assertEqual(True, agent.expect_trace())

  def test_extract_tgids(self):
    with contextlib.nested(open(ATRACE_PROCFS_DUMP, 'r'),
                           open(ATRACE_EXTRACTED_TGIDS, 'r')) as (f1, f2):

      atrace_procfs_dump = f1.read()
      atrace_procfs_extracted = f2.read()

      tgids = eval(atrace_procfs_extracted)
      result = atrace_agent.extract_tgids(atrace_procfs_dump)

      self.assertEqual(result, tgids)

  def test_fix_missing_tgids(self):
    with contextlib.nested(open(ATRACE_EXTRACTED_TGIDS, 'r'),
                           open(ATRACE_MISSING_TGIDS, 'r'),
                           open(ATRACE_FIXED_TGIDS, 'r')) as (f1, f2, f3):

      atrace_data = f2.read()
      tgid_map = eval(f1.read())
      fixed = f3.read()

      res = atrace_agent.fix_missing_tgids(atrace_data, tgid_map)
      self.assertEqual(res, fixed)


class AtraceLegacyAgentTest(unittest.TestCase):

  def test_construct_trace_command(self):
    options, categories = systrace.parse_options(SYSTRACE_CMD)
    agent = atrace_agent.AtraceLegacyAgent(options, categories)
    tracer_args = agent._construct_trace_command()
    self.assertEqual(' '.join(LEGACY_TRACE_CMD), ' '.join(tracer_args))
    self.assertEqual(True, agent.expect_trace())


class BootAgentTest(unittest.TestCase):

  def test_boot(self):
    options, categories = systrace.parse_options(SYSTRACE_BOOT_CMD)
    agent = atrace_agent.BootAgent(options, categories)
    tracer_args = agent._construct_trace_command()
    self.assertEqual(' '.join(TRACE_BOOT_CMD), ' '.join(tracer_args))
    self.assertEqual(True, agent.expect_trace())
