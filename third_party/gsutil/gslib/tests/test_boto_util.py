# -*- coding: utf-8 -*-
# Copyright 2020 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for boto_util.py."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from gslib import cloud_api
from gslib.utils import boto_util
from gslib import context_config
from gslib.tests import testcase
from gslib.tests.testcase import base
from gslib.tests.util import unittest

from six import add_move, MovedModule

add_move(MovedModule('mock', 'mock', 'unittest.mock'))
from six.moves import mock


class TestBotoUtil(testcase.GsUtilUnitTestCase):
  """Test utils that make use of the Boto dependency."""

  @mock.patch.object(context_config, 'get_context_config')
  def testSetsHostBaseToMtlsIfClientCertificateEnabled(self,
                                                       mock_get_context_config):
    mock_context_config = mock.Mock()
    mock_context_config.use_client_certificate = True
    mock_context_config.client_cert_path = 'path'
    mock_context_config.client_cert_password = 'password'
    mock_get_context_config.return_value = mock_context_config

    mock_http_class = mock.Mock(return_value=mock.Mock())
    mock_http = boto_util.GetNewHttp(mock_http_class)
    mock_http.add_certificate.assert_called_once_with(
        key='path',
        cert='path',
        domain='',
        password='password',
    )
