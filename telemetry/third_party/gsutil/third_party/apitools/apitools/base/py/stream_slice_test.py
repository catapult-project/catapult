"""Tests for stream_slice."""

import string

import six
import unittest2

from apitools.base.py import exceptions
from apitools.base.py import stream_slice


class StreamSliceTest(unittest2.TestCase):

    def setUp(self):
        self.stream = six.StringIO(string.ascii_letters)
        self.value = self.stream.getvalue()
        self.stream.seek(0)

    def testSimpleSlice(self):
        ss = stream_slice.StreamSlice(self.stream, 10)
        self.assertEqual('', ss.read(0))
        self.assertEqual(self.value[0:3], ss.read(3))
        self.assertIn('7/10', str(ss))
        self.assertEqual(self.value[3:10], ss.read())
        self.assertEqual('', ss.read())
        self.assertEqual('', ss.read(10))
        self.assertEqual(10, self.stream.tell())

    def testEmptySlice(self):
        ss = stream_slice.StreamSlice(self.stream, 0)
        self.assertEqual('', ss.read(5))
        self.assertEqual('', ss.read())
        self.assertEqual(0, self.stream.tell())

    def testOffsetStream(self):
        self.stream.seek(26)
        ss = stream_slice.StreamSlice(self.stream, 26)
        self.assertEqual(self.value[26:36], ss.read(10))
        self.assertEqual(self.value[36:], ss.read())
        self.assertEqual('', ss.read())

    def testTooShortStream(self):
        ss = stream_slice.StreamSlice(self.stream, 1000)
        self.assertEqual(self.value, ss.read())
        self.assertEqual('', ss.read(0))
        with self.assertRaises(exceptions.StreamExhausted) as e:
            ss.read()
        with self.assertRaises(exceptions.StreamExhausted) as e:
            ss.read(10)
        self.assertIn('exhausted after %d' % len(self.value), str(e.exception))
