# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A dummy exception subclass used by core/discover.py's unit tests."""
from __future__ import absolute_import
from discoverable_classes import discover_dummyclass

class DummyExceptionWithParameterImpl2(discover_dummyclass.DummyException):
  def __init__(self, parameter1, parameter2):
    # TODO(https://crbug.com/1262295): Change to super() after Python2 trybots retire.
    # pylint: disable=super-with-arguments
    super(DummyExceptionWithParameterImpl2, self).__init__()
    del parameter1, parameter2
