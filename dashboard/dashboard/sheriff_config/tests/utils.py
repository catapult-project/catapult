# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" Utilities for testing """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from apiclient.http import HttpMockSequence

with open('tests/config-discovery.json') as discovery_file:
  _CONFIG = discovery_file.read()


def HttpMockSequenceWithDiscovery(sequence):
  discovery_sequence = [
      ({
          'status': '200'
      }, _CONFIG),
  ]
  return HttpMockSequence(discovery_sequence + sequence)
