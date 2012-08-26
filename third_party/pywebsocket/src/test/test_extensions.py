#!/usr/bin/env python
#
# Copyright 2012, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""Tests for extensions module."""


import unittest

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket import common
from mod_pywebsocket import extensions


class PerFrameCompressionExtensionTest(unittest.TestCase):
    """A unittest for the perframe-compression extension."""

    def test_parse_method_simple(self):
        method_list = extensions._parse_compression_method('foo')
        self.assertEqual(1, len(method_list))
        method = method_list[0]
        self.assertEqual('foo', method.name())
        self.assertEqual(0, len(method.get_parameters()))

    def test_parse_method_with_parameter(self):
        method_list = extensions._parse_compression_method('foo; x; y=10')
        self.assertEqual(1, len(method_list))
        method = method_list[0]
        self.assertEqual('foo', method.name())
        self.assertEqual(2, len(method.get_parameters()))
        self.assertTrue(method.has_parameter('x'))
        self.assertEqual(None, method.get_parameter_value('x'))
        self.assertTrue(method.has_parameter('y'))
        self.assertEqual('10', method.get_parameter_value('y'))

    def test_parse_method_with_quoted_parameter(self):
        method_list = extensions._parse_compression_method(
            'foo; x="Hello World"; y=10')
        self.assertEqual(1, len(method_list))
        method = method_list[0]
        self.assertEqual('foo', method.name())
        self.assertEqual(2, len(method.get_parameters()))
        self.assertTrue(method.has_parameter('x'))
        self.assertEqual('Hello World', method.get_parameter_value('x'))
        self.assertTrue(method.has_parameter('y'))
        self.assertEqual('10', method.get_parameter_value('y'))
        
    def test_parse_method_multiple(self):
        method_list = extensions._parse_compression_method('foo, bar')
        self.assertEqual(2, len(method_list))
        self.assertEqual('foo', method_list[0].name())
        self.assertEqual(0, len(method_list[0].get_parameters()))
        self.assertEqual('bar', method_list[1].name())
        self.assertEqual(0, len(method_list[1].get_parameters()))

    def test_parse_method_multiple_methods_with_quoted_parameter(self):
        method_list = extensions._parse_compression_method(
            'foo; x="Hello World", bar; y=10')
        self.assertEqual(2, len(method_list))
        self.assertEqual('foo', method_list[0].name())
        self.assertEqual(1, len(method_list[0].get_parameters()))
        self.assertTrue(method_list[0].has_parameter('x'))
        self.assertEqual('Hello World',
                         method_list[0].get_parameter_value('x'))
        self.assertEqual('bar', method_list[1].name())
        self.assertEqual(1, len(method_list[1].get_parameters()))
        self.assertTrue(method_list[1].has_parameter('y'))
        self.assertEqual('10', method_list[1].get_parameter_value('y'))

    def test_create_method_desc_simple(self):
        params = common.ExtensionParameter('foo')
        desc = extensions._create_accepted_method_desc('foo',
                                                       params.get_parameters())
        self.assertEqual('foo', desc)

    def test_create_method_desc_with_parameters(self):
        params = common.ExtensionParameter('foo')
        params.add_parameter('x', 'Hello, World')
        params.add_parameter('y', '10')
        desc = extensions._create_accepted_method_desc('foo',
                                                       params.get_parameters())
        self.assertEqual('foo; x="Hello, World"; y=10', desc)


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
