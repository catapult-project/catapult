"""Unit tests for oauth2client.util."""

import mock
import unittest2

from oauth2client import util


__author__ = 'jcgregorio@google.com (Joe Gregorio)'



class PositionalTests(unittest2.TestCase):

    def test_usage(self):
        util.positional_parameters_enforcement = util.POSITIONAL_EXCEPTION

        # 1 positional arg, 1 keyword-only arg.
        @util.positional(1)
        def fn(pos, kwonly=None):
            return True

        self.assertTrue(fn(1))
        self.assertTrue(fn(1, kwonly=2))
        self.assertRaises(TypeError, fn, 1, 2)

        # No positional, but a required keyword arg.
        @util.positional(0)
        def fn2(required_kw):
            return True

        self.assertTrue(fn2(required_kw=1))
        self.assertRaises(TypeError, fn2, 1)

        # Unspecified positional, should automatically figure out 1 positional
        # 1 keyword-only (same as first case above).
        @util.positional
        def fn3(pos, kwonly=None):
            return True

        self.assertTrue(fn3(1))
        self.assertTrue(fn3(1, kwonly=2))
        self.assertRaises(TypeError, fn3, 1, 2)


    @mock.patch('oauth2client.util.logger')
    def test_enforcement_warning(self, mock_logger):
        util.positional_parameters_enforcement = util.POSITIONAL_WARNING

        @util.positional(1)
        def fn(pos, kwonly=None):
            return True

        self.assertTrue(fn(1, 2))
        self.assertTrue(mock_logger.warning.called)


    @mock.patch('oauth2client.util.logger')
    def test_enforcement_ignore(self, mock_logger):
        util.positional_parameters_enforcement = util.POSITIONAL_IGNORE

        @util.positional(1)
        def fn(pos, kwonly=None):
            return True

        self.assertTrue(fn(1, 2))
        self.assertFalse(mock_logger.warning.called)


class ScopeToStringTests(unittest2.TestCase):

    def test_iterables(self):
        cases = [
            ('', ''),
            ('', ()),
            ('', []),
            ('', ('',)),
            ('', ['', ]),
            ('a', ('a',)),
            ('b', ['b', ]),
            ('a b', ['a', 'b']),
            ('a b', ('a', 'b')),
            ('a b', 'a b'),
            ('a b', (s for s in ['a', 'b'])),
        ]
        for expected, case in cases:
            self.assertEqual(expected, util.scopes_to_string(case))


class StringToScopeTests(unittest2.TestCase):

    def test_conversion(self):
        cases = [
            (['a', 'b'], ['a', 'b']),
            ('', []),
            ('a', ['a']),
            ('a b c d e f', ['a', 'b', 'c', 'd', 'e', 'f']),
        ]

        for case, expected in cases:
            self.assertEqual(expected, util.string_to_scopes(case))



class AddQueryParameterTests(unittest2.TestCase):

    def test__add_query_parameter(self):
        self.assertEqual(
            util._add_query_parameter('/action', 'a', None),
            '/action')
        self.assertEqual(
            util._add_query_parameter('/action', 'a', 'b'),
            '/action?a=b')
        self.assertEqual(
            util._add_query_parameter('/action?a=b', 'a', 'c'),
            '/action?a=c')
        # Order is non-deterministic.
        self.assertIn(
            util._add_query_parameter('/action?a=b', 'c', 'd'),
            ['/action?a=b&c=d', '/action?c=d&a=b'])
        self.assertEqual(
            util._add_query_parameter('/action', 'a', ' ='),
            '/action?a=+%3D')

if __name__ == '__main__':  # pragma: NO COVER
    unittest2.main()
