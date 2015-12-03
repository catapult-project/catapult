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

"""Internal Datastore model for the Tunes DB.

The Tunes DB is a simple polymophic structure composed of polymorphic
Info entities.  Artists and Albums are represented.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import re

from google.appengine.ext import db
from google.appengine.ext.db import polymodel


_SEARCH_NAME_REGEX = re.compile('\w+', re.UNICODE)


def _normalize_name(name):
  """Helper used to convert a user entered name in to search compatible string.

  In order to make search as error free as possible, names of info records
  are converted to a simplified utf-8 encoded string that makes prefix searches
  easy.  to make searching simpler, it removes all extra punctuation and spaces.

  Examples:
    _normalize_name('Duke Ellington') == 'duke ellington'
    _normalize_name('  Duke  Ellington  ') == 'duke ellington'
    _normalize_name('Duke-Ellington!') == 'duke ellington'
    _normalize_name('Duke_Ellington') == 'duke ellington'
    _normalize_name(u'Duk\xea Ellington') == 'Duk\xc3\xaa Ellington'

  Args:
    name: Name to convert to search string.

  Returns:
    Lower case, single space separated ByteString of name with punctuation
    removed.  Unicode values are converted to UTF-8 encoded string.
  """
  if name is None:
    return None
  elif isinstance(name, str):
    name = name.decode('utf-8')

  # Must explicitly replace '_' because the \w re part does not
  name = name.replace(u'_', u' ')

  names = _SEARCH_NAME_REGEX.findall(name)
  name = ' '.join(names)
  return db.ByteString(name.lower().encode('utf-8'))


class Info(polymodel.PolyModel):
  """Base class for all Info records in Tunes DB.

  Properties:
    name: User friendly name for record.
    encoded_name: Derived from name to allow easy prefix searching.  Name is
      transformed using _normalize_name.
  """

  name = db.StringProperty()

  @db.ComputedProperty
  def encoded_name(self):
    return _normalize_name(self.name)

  @classmethod
  def search(cls, name_prefix=None):
    """Create search query based on info record name prefix.

    Args:
      name_prefix: User input name-prefix to search for.  If name_prefix
      is empty string or None returns all records of Info sub-class.  Records
      are sorted by their encoded name.

    Returns:
      Datastore query pointing to search results.
    """
    name_prefix = _normalize_name(name_prefix)
    query = cls.all().order('encoded_name')
    if name_prefix:
      query.filter('encoded_name >=', db.ByteString(name_prefix))
      # Do not need to worry about name_prefix + '\xff\xff' because not
      # a unicode character.
      query.filter('encoded_name <=', db.ByteString(name_prefix + '\xff'))
    return query


class ArtistInfo(Info):
  """Musician or music group responsible for recording.

  Properties:
    album_count: Number of albums produced by artist.
    albums: Implicit collection of albums produced by artist.
  """

  album_count = db.IntegerProperty(default=0)


class AlbumInfo(Info):
  """Album produced by a musician or music group.

  Properties:
    artist: Artist that produced album.
    released: Year that album was released.
  """

  artist = db.ReferenceProperty(ArtistInfo,
                                collection_name='albums',
                                required=True)
  released = db.IntegerProperty()
