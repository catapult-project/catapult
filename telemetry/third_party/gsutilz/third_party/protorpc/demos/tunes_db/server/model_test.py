#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
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
#

"""Tests for model."""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import unittest

from google.appengine.ext import db

import datastore_test_util
import model


class InfoTest(datastore_test_util.DatastoreTest):
  """Test the info base class.

  This test uses the ArtistInfo sub-class, but the functionality defined
  there will work for all sub-classes.
  """

  def testEncodedName(self):
    """Test the encoded_name derived property."""

    def get_encoded_name(name):
      """Helper to get encoded name for an provided name.

      Args:
        name: Encoded name to convert to encoded_name.
      """
      return db.get(model.ArtistInfo(name=name).put()).encoded_name

    # Normal strings.
    self.assertEquals('stereo total', get_encoded_name('Stereo Total'))
    # Not alphabetic characters.
    self.assertEquals('the go team', get_encoded_name('The Go! Team'))
    # Unecessary spaces.
    self.assertEquals('ananda shankar',
                      get_encoded_name('  Ananda  Shankar  '))
    # Non-ascii unicode.
    self.assertEquals('vive la f\xc3\xaate',
                      get_encoded_name(u'Vive la f\xeate'))
    # Numerics.
    self.assertEquals('delta5', get_encoded_name(u'Delta5'))

    # The pesky '_'.
    self.assertEquals('wendy carlos', get_encoded_name('Wendy__Carlos'))

  def testSearch(self):
    """Test searching by name prefix."""
    # Defined out of order to make sure search is in order.
    model.ArtistInfo(name='The  Bee__Gees').put()
    model.ArtistInfo(name='  The-DooRs  ').put()
    model.ArtistInfo(name='Wendy Carlos').put()
    model.ArtistInfo(name='Amadeus Mozart').put()
    model.ArtistInfo(name='The Beatles').put()

    names = [artist.name for artist in model.ArtistInfo.search('  ')]
    self.assertEquals(['Amadeus Mozart', 'The Beatles', 'The  Bee__Gees',
                       '  The-DooRs  ', 'Wendy Carlos'],
                      names)

    names = [artist.name for artist in model.ArtistInfo.search('  !tHe}  ')]
    self.assertEquals(['The Beatles', 'The  Bee__Gees', '  The-DooRs  '], names)

    names = [artist.name for artist in model.ArtistInfo.search('the bee gees')]
    self.assertEquals(['The  Bee__Gees'], names)

    names = [artist.name for artist in model.ArtistInfo.search('the  doors')]
    self.assertEquals(['  The-DooRs  '], names)


if __name__ == '__main__':
  unittest.main()
