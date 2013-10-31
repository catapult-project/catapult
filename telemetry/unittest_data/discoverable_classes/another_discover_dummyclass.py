# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""More dummy exception subclasses used by core/discover.py's unit tests."""

# Import class instead of module explicitly so that inspect.getmembers() returns
# two Exception subclasses in this current file.
# Suppress complaints about unable to import class.  The directory path is
# added at runtime by telemetry test runner.
#pylint: disable=F0401
from discoverable_classes.discover_dummyclass import DummyException


class _PrivateDummyException(DummyException):
  pass


class DummyExceptionImpl1(_PrivateDummyException):
  pass


class DummyExceptionImpl2(_PrivateDummyException):
  pass
