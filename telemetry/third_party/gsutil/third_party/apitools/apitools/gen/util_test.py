"""Tests for util."""
import unittest2

from apitools.gen import util


class NormalizeVersionTest(unittest2.TestCase):

    def testVersions(self):
        already_valid = 'v1'
        self.assertEqual(already_valid, util.NormalizeVersion(already_valid))
        to_clean = 'v0.1'
        self.assertEqual('v0_1', util.NormalizeVersion(to_clean))


class NamesTest(unittest2.TestCase):

    def testKeywords(self):
        names = util.Names([''])
        self.assertEqual('in_', names.CleanName('in'))

    def testNormalizeEnumName(self):
        names = util.Names([''])
        self.assertEqual('_0', names.NormalizeEnumName('0'))
