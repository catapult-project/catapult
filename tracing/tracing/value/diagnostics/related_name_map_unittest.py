# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram_unittest
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import related_name_map


class RelatedNameMapUnittest(unittest.TestCase):
  def testRoundtrip(self):
    names = related_name_map.RelatedNameMap()
    names.Set('a', 'A')
    d = names.AsDict()
    clone = diagnostic.Diagnostic.FromDict(d)
    self.assertEqual(
        histogram_unittest.ToJSON(d), histogram_unittest.ToJSON(clone.AsDict()))
    self.assertEqual(clone.Get('a'), 'A')

  def testMerge(self):
    a_names = related_name_map.RelatedNameMap()
    a_names.Set('a', 'A')
    b_names = related_name_map.RelatedNameMap()
    b_names.Set('b', 'B')
    self.assertTrue(a_names.CanAddDiagnostic(b_names))
    self.assertTrue(b_names.CanAddDiagnostic(a_names))
    self.assertFalse(a_names.CanAddDiagnostic(generic_set.GenericSet([])))

    a_names.AddDiagnostic(b_names)
    self.assertEqual(a_names.Get('b'), 'B')
    a_names.AddDiagnostic(b_names)
    self.assertEqual(a_names.Get('b'), 'B')

    b_names.Set('a', 'C')
    with self.assertRaises(ValueError):
      a_names.AddDiagnostic(b_names)

  def testEquals(self):
    a_names = related_name_map.RelatedNameMap()
    a_names.Set('a', 'A')
    self.assertNotEqual(a_names, generic_set.GenericSet([]))
    b_names = related_name_map.RelatedNameMap()
    self.assertNotEqual(a_names, b_names)
    b_names.Set('a', 'B')
    self.assertNotEqual(a_names, b_names)
    b_names.Set('a', 'A')
    self.assertEqual(a_names, b_names)
