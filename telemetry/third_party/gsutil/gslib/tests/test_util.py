# -*- coding: utf-8 -*-
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
"""Tests for gsutil utility functions."""

from __future__ import absolute_import

import httplib2
from gslib import util
import gslib.tests.testcase as testcase
from gslib.tests.util import SetEnvironmentForTest
from gslib.util import CompareVersions


class TestUtil(testcase.GsUtilUnitTestCase):
  """Tests for utility functions."""

  def test_MakeHumanReadable(self):
    """Tests converting byte counts to human-readable strings."""
    self.assertEqual(util.MakeHumanReadable(0), '0 B')
    self.assertEqual(util.MakeHumanReadable(1023), '1023 B')
    self.assertEqual(util.MakeHumanReadable(1024), '1 KiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 2), '1 MiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 3), '1 GiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 3 * 5.3), '5.3 GiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 4 * 2.7), '2.7 TiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 5), '1 PiB')
    self.assertEqual(util.MakeHumanReadable(1024 ** 6), '1 EiB')

  def test_MakeBitsHumanReadable(self):
    """Tests converting bit counts to human-readable strings."""
    self.assertEqual(util.MakeBitsHumanReadable(0), '0 bit')
    self.assertEqual(util.MakeBitsHumanReadable(1023), '1023 bit')
    self.assertEqual(util.MakeBitsHumanReadable(1024), '1 Kibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 2), '1 Mibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 3), '1 Gibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 3 * 5.3), '5.3 Gibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 4 * 2.7), '2.7 Tibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 5), '1 Pibit')
    self.assertEqual(util.MakeBitsHumanReadable(1024 ** 6), '1 Eibit')

  def test_HumanReadableToBytes(self):
    """Tests converting human-readable strings to byte counts."""
    self.assertEqual(util.HumanReadableToBytes('1'), 1)
    self.assertEqual(util.HumanReadableToBytes('15'), 15)
    self.assertEqual(util.HumanReadableToBytes('15.3'), 15)
    self.assertEqual(util.HumanReadableToBytes('15.7'), 16)
    self.assertEqual(util.HumanReadableToBytes('1023'), 1023)
    self.assertEqual(util.HumanReadableToBytes('1k'), 1024)
    self.assertEqual(util.HumanReadableToBytes('2048'), 2048)
    self.assertEqual(util.HumanReadableToBytes('1 k'), 1024)
    self.assertEqual(util.HumanReadableToBytes('1 K'), 1024)
    self.assertEqual(util.HumanReadableToBytes('1 KB'), 1024)
    self.assertEqual(util.HumanReadableToBytes('1 KiB'), 1024)
    self.assertEqual(util.HumanReadableToBytes('1 m'), 1024 ** 2)
    self.assertEqual(util.HumanReadableToBytes('1 M'), 1024 ** 2)
    self.assertEqual(util.HumanReadableToBytes('1 MB'), 1024 ** 2)
    self.assertEqual(util.HumanReadableToBytes('1 MiB'), 1024 ** 2)
    self.assertEqual(util.HumanReadableToBytes('1 g'), 1024 ** 3)
    self.assertEqual(util.HumanReadableToBytes('1 G'), 1024 ** 3)
    self.assertEqual(util.HumanReadableToBytes('1 GB'), 1024 ** 3)
    self.assertEqual(util.HumanReadableToBytes('1 GiB'), 1024 ** 3)
    self.assertEqual(util.HumanReadableToBytes('1t'), 1024 ** 4)
    self.assertEqual(util.HumanReadableToBytes('1T'), 1024 ** 4)
    self.assertEqual(util.HumanReadableToBytes('1TB'), 1024 ** 4)
    self.assertEqual(util.HumanReadableToBytes('1TiB'), 1024 ** 4)
    self.assertEqual(util.HumanReadableToBytes('1\t   p'), 1024 ** 5)
    self.assertEqual(util.HumanReadableToBytes('1\t   P'), 1024 ** 5)
    self.assertEqual(util.HumanReadableToBytes('1\t   PB'), 1024 ** 5)
    self.assertEqual(util.HumanReadableToBytes('1\t   PiB'), 1024 ** 5)
    self.assertEqual(util.HumanReadableToBytes('1e'), 1024 ** 6)
    self.assertEqual(util.HumanReadableToBytes('1E'), 1024 ** 6)
    self.assertEqual(util.HumanReadableToBytes('1EB'), 1024 ** 6)
    self.assertEqual(util.HumanReadableToBytes('1EiB'), 1024 ** 6)

  def test_CompareVersions(self):
    """Tests CompareVersions for various use cases."""
    # CompareVersions(first, second) returns (g, m), where
    #   g is True if first known to be greater than second, else False.
    #   m is True if first known to be greater by at least 1 major version,
    (g, m) = CompareVersions('3.37', '3.2')
    self.assertTrue(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('7', '2')
    self.assertTrue(g)
    self.assertTrue(m)
    (g, m) = CompareVersions('3.32', '3.32pre')
    self.assertTrue(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.32pre', '3.31')
    self.assertTrue(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.4pre', '3.3pree')
    self.assertTrue(g)
    self.assertFalse(m)

    (g, m) = CompareVersions('3.2', '3.37')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('2', '7')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.32pre', '3.32')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.31', '3.32pre')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.3pre', '3.3pre')
    self.assertFalse(g)
    self.assertFalse(m)

    (g, m) = CompareVersions('foobar', 'baz')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.32', 'baz')
    self.assertFalse(g)
    self.assertFalse(m)

    (g, m) = CompareVersions('3.4', '3.3')
    self.assertTrue(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('3.3', '3.4')
    self.assertFalse(g)
    self.assertFalse(m)
    (g, m) = CompareVersions('4.1', '3.33')
    self.assertTrue(g)
    self.assertTrue(m)
    (g, m) = CompareVersions('3.10', '3.1')
    self.assertTrue(g)
    self.assertFalse(m)

  def _AssertProxyInfosEqual(self, pi1, pi2):
    self.assertEqual(pi1.proxy_type, pi2.proxy_type)
    self.assertEqual(pi1.proxy_host, pi2.proxy_host)
    self.assertEqual(pi1.proxy_port, pi2.proxy_port)
    self.assertEqual(pi1.proxy_rdns, pi2.proxy_rdns)
    self.assertEqual(pi1.proxy_user, pi2.proxy_user)
    self.assertEqual(pi1.proxy_pass, pi2.proxy_pass)

  def test_ProxyInfoFromEnvironmentVar(self):
    """Tests ProxyInfoFromEnvironmentVar for various cases."""
    valid_variables = ['http_proxy', 'https_proxy']
    if not util.IS_WINDOWS:
      # Dynamically set Windows environment variables are case-insensitive.
      valid_variables.append('HTTPS_PROXY')
    # Clear any existing environment variables for the duration of the test.
    clear_dict = {}
    for key in valid_variables:
      clear_dict[key] = None
    with SetEnvironmentForTest(clear_dict):
      for env_var in valid_variables:
        for url_string in ['hostname', 'http://hostname', 'https://hostname']:
          with SetEnvironmentForTest({env_var: url_string}):
            self._AssertProxyInfosEqual(
                util.ProxyInfoFromEnvironmentVar(env_var),
                httplib2.ProxyInfo(
                    httplib2.socks.PROXY_TYPE_HTTP, 'hostname',
                    443 if env_var.lower().startswith('https') else 80))
            # Shouldn't populate info for other variables
            for other_env_var in valid_variables:
              if other_env_var == env_var: continue
              self._AssertProxyInfosEqual(
                  util.ProxyInfoFromEnvironmentVar(other_env_var),
                  httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, None, 0))
        for url_string in ['1.2.3.4:50', 'http://1.2.3.4:50',
                           'https://1.2.3.4:50']:
          with SetEnvironmentForTest({env_var: url_string}):
            self._AssertProxyInfosEqual(
                util.ProxyInfoFromEnvironmentVar(env_var),
                httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, '1.2.3.4',
                                   50))
        for url_string in ['foo:bar@1.2.3.4:50', 'http://foo:bar@1.2.3.4:50',
                           'https://foo:bar@1.2.3.4:50']:
          with SetEnvironmentForTest({env_var: url_string}):
            self._AssertProxyInfosEqual(
                util.ProxyInfoFromEnvironmentVar(env_var),
                httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP,
                                   '1.2.3.4', 50, proxy_user='foo',
                                   proxy_pass='bar'))
        for url_string in ['bar@1.2.3.4:50', 'http://bar@1.2.3.4:50',
                           'https://bar@1.2.3.4:50']:
          with SetEnvironmentForTest({env_var: url_string}):
            self._AssertProxyInfosEqual(
                util.ProxyInfoFromEnvironmentVar(env_var),
                httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, '1.2.3.4',
                                   50, proxy_pass='bar'))
      for env_var in ['proxy', 'noproxy', 'garbage']:
        for url_string in ['1.2.3.4:50', 'http://1.2.3.4:50']:
          with SetEnvironmentForTest({env_var: url_string}):
            self._AssertProxyInfosEqual(
                util.ProxyInfoFromEnvironmentVar(env_var),
                httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, None, 0))
