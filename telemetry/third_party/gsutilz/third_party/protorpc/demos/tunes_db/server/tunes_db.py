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

"""Tunes DB service implementation.

This module contains all the protocol buffer and service definitions
necessary for the Tunes DB service.
"""

import base64
import sys

from google.appengine.ext import db

from protorpc import descriptor
from protorpc import message_types
from protorpc import messages
from protorpc import protobuf
from protorpc import remote

import model


class Artist(messages.Message):
  """Musician or music group responsible for music production.

  Fields:
    artist_id: Unique opaque identifier for artist.
    name: User friendly name of artist.
    album_count: Number of albums produced by artist.
  """

  artist_id = messages.StringField(1, required=True)
  name = messages.StringField(2, required=True)

  album_count = messages.IntegerField(3)


class Album(messages.Message):
  """Album produced by a musician or music group.

  Fields:
    album_id: Unique opaque identifier for artist.
    artist_id: Artist id of musician or music group that produced album.
    name: Name of album.
    released: Year when album was released.
  """

  album_id = messages.StringField(1, required=True)
  artist_id = messages.StringField(2, required=True)
  name = messages.StringField(3, required=True)
  released = messages.IntegerField(4)


class AddArtistRequest(messages.Message):
  """Request to add a new Artist to library.

  Fields:
    name: User friendly name of artist.
  """

  name = messages.StringField(1, required=True)


class AddArtistResponse(messages.Message):
  """Response sent after creation of new artist in library.

  Fields:
    artist_id: Unique opaque ID of new artist.
  """

  artist_id = messages.StringField(1, required=True)


class UpdateArtistRequest(messages.Message):
  """Update an existing artist.

  Fields:
    artist: Complete information about artist to update.
  """

  artist = messages.MessageField(Artist, 1, required=True)


class UpdateArtistResponse(messages.Message):
  """Artist update response.

  Fields:
    artist_updated: Artist was found and updated.
  """

  artist_updated = messages.BooleanField(1, required=True)


class DeleteArtistRequest(messages.Message):
  """Delete artist from library.

  Fields:
    artist_id: Unique opaque ID of artist to delete.
  """

  artist_id = messages.StringField(1, required=True)


class DeleteArtistResponse(messages.Message):
  """Artist deletion response.

  Fields:
    artist_deleted: Artist was found and deleted.
  """

  artist_deleted = messages.BooleanField(1, default=True)


class FetchArtistRequest(messages.Message):
  """Fetch an artist from the library.

  Fields:
    artist_id: Unique opaque ID of artist to fetch.
  """

  artist_id = messages.StringField(1, required=True)


class FetchArtistResponse(messages.Message):
  """Fetched artist from library.

  Fields:
    artist: Artist found in library.
  """

  artist = messages.MessageField(Artist, 1)


class SearchArtistsRequest(messages.Message):
  """Artist search request.

  Fields:
    continuation: Continuation from the response of a previous call to
      search_artists remote method.
    fetch_size: Maximum number of records to retrieve.
    name_prefix: Name prefix of artists to search.  If none provided and
      no continuation provided, search will be of all artists in library.
      If continuation is provided, name_prefix should be empty, if not, value
      is ignored.
  """

  continuation = messages.StringField(1)
  fetch_size = messages.IntegerField(2, default=10)
  name_prefix = messages.StringField(3, default=u'')


class SearchArtistsResponse(messages.Message):
  """Response from searching artists.

  Fields:
    artists: Artists found from search up to fetch_size.
    continuation: Opaque string that can be used with a new search request
      that will continue finding new artists where this response left off.
      Will not be set if there were no results from the search or fewer
      artists were returned in the response than requested, indicating the end
      of the query.
  """

  artists = messages.MessageField(Artist, 1, repeated=True)
  continuation = messages.StringField(2)


class AddAlbumRequest(messages.Message):
  """Request to add a new album to library.

  Fields:
    name: User friendly name of album.
    artist_id: Artist id of artist that produced record.
    released: Year album was released.
  """

  name = messages.StringField(1, required=True)
  artist_id = messages.StringField(2, required=True)
  released = messages.IntegerField(3)


class AddAlbumResponse(messages.Message):
  """Response sent after creation of new album in library.

  Fields:
    album_id: Unique opaque ID of new album.
  """

  album_id = messages.StringField(1, required=True)


class UpdateAlbumRequest(messages.Message):
  """Update an existing album.

  Fields:
    album: Complete information about album to update.
  """

  album = messages.MessageField(Album, 1, required=True)


class UpdateAlbumResponse(messages.Message):
  """Album update response.

  Fields:
    album_updated: Album was found and updated.
  """

  album_updated = messages.BooleanField(1, required=True)


class DeleteAlbumRequest(messages.Message):
  """Delete album from library.

  Fields:
    album_id: Unique opaque ID of album to delete.
  """

  album_id = messages.StringField(1, required=True)


class DeleteAlbumResponse(messages.Message):
  """Album deletion response.

  Fields:
    album_deleted: Album was found and deleted.
  """

  album_deleted = messages.BooleanField(1, default=True)


class FetchAlbumRequest(messages.Message):
  """Fetch an album from the library.

  Fields:
    album_id: Unique opaque ID of album to fetch.
  """

  album_id = messages.StringField(1, required=True)


class FetchAlbumResponse(messages.Message):
  """Fetched album from library.

  Fields:
    album: Album found in library.
  """

  album = messages.MessageField(Album, 1)


class SearchAlbumsRequest(messages.Message):
  """Album search request.

  Fields:
    continuation: Continuation from the response of a previous call to
      search_albums remote method.
    fetch_size: Maximum number of records to retrieve.
    name_prefix: Name prefix of albms to search.  If none provided and
      no continuation provided, search will be of all albums in library.
      If continuation is provided, name_prefix should be empty, if not, value
      is ignored.
    artist_id: Restrict search to albums of single artist.
  """

  continuation = messages.StringField(1)
  fetch_size = messages.IntegerField(2, default=10)
  name_prefix = messages.StringField(3, default=u'')
  artist_id = messages.StringField(4)


class SearchAlbumsResponse(messages.Message):
  """Response from searching artists.

  Fields:
    albums: Albums found from search up to fetch_size.
    continuation: Opaque string that can be used with a new search request
      that will continue finding new albums where this response left off.
      Will not be set if there were no results from the search or fewer
      albums were returned in the response than requested, indicating the end
      of the query.
  """

  albums = messages.MessageField(Album, 1, repeated=True)
  continuation = messages.StringField(2)


class MusicLibraryService(remote.Service):
  """Music library service."""

  __file_set = None

  def __artist_from_model(self, artist_model):
    """Helper that copies an Artist model to an Artist message.

    Args:
      artist_model: model.ArtistInfo instance to convert in to an Artist
        message.

    Returns:
      New Artist message with contents of artist_model copied in to it.
    """
    return Artist(artist_id=unicode(artist_model.key()),
                  name=artist_model.name,
                  album_count=artist_model.album_count)

  def __album_from_model(self, album_model):
    """Helper that copies an Album model to an Album message.

    Args:
      album_model: model.AlbumInfo instance to convert in to an Album
        message.

    Returns:
      New Album message with contents of album_model copied in to it.
    """
    artist_id = model.AlbumInfo.artist.get_value_for_datastore(album_model)

    return Album(album_id=unicode(album_model.key()),
                 artist_id=unicode(artist_id),
                 name=album_model.name,
                 released=album_model.released or None)

  @classmethod
  def __search_info(cls,
                    request,
                    info_class,
                    model_to_message,
                    customize_query=None):
    """Search over an Info subclass.

    Since all search request classes are very similar, it's possible to
    generalize how to do searches over them.

    Args:
      request: Search request received from client.
      info_class: The model.Info subclass to search.
      model_to_method: Function (model) -> message that transforms an instance
        of info_class in to the appropriate messages.Message subclass.
      customize_query: Function (request, query) -> None that adds additional
        filters to Datastore query based on specifics of that search message.

    Returns:
      Tuple (results, continuation):
        results: A list of messages satisfying the parameters of the request.
          None if there are no results.
        continuation: Continuation string for response if there are more
          results available.  None if there are no more results available.
    """
    # TODO(rafek): fetch_size from this request should take priority
    # over what is stored in continuation.
    if request.continuation:
      encoded_search, continuation = request.continuation.split(':', 1)
      decoded_search = base64.urlsafe_b64decode(encoded_search.encode('utf-8'))
      request = protobuf.decode_message(type(request), decoded_search)
    else:
      continuation = None
      encoded_search = unicode(base64.urlsafe_b64encode(
          protobuf.encode_message(request)))

    name_prefix = request.name_prefix

    query = info_class.search(name_prefix)
    query.order('name')
    if customize_query:
      customize_query(request, query)

    if continuation:
      # TODO(rafek): Pure query cursors are not safe for model with
      # query restrictions.  Would technically need to be encrypted.
      query.with_cursor(continuation)

    fetch_size = request.fetch_size

    model_instance = query.fetch(fetch_size)
    results = None
    continuation = None
    if model_instance:
      results = [model_to_message(i) for i in model_instance]
      if len(model_instance) == fetch_size:
        cursor = query.cursor()
        continuation = u'%s:%s' % (encoded_search, query.cursor())

    return results, continuation


  @remote.method(AddArtistRequest, AddArtistResponse)
  def add_artist(self, request):
    """Add artist to library."""
    artist_name = request.name
    def do_add():
      artist = model.ArtistInfo(name=artist_name)
      artist.put()
      return artist
    artist = db.run_in_transaction(do_add)

    return AddArtistResponse(artist_id = unicode(artist.key()))

  @remote.method(UpdateArtistRequest, UpdateArtistResponse)
  def update_artist(self, request):
    """Update artist from library."""
    def do_deletion():
      artist = model.ArtistInfo.get(request.artist.artist_id)
      if artist:
        artist.name = request.artist.name
        artist.put()
        return True
      else:
        return False
    return UpdateArtistResponse(
      artist_updated=db.run_in_transaction(do_deletion))

  @remote.method(DeleteArtistRequest, DeleteArtistResponse)
  def delete_artist(self, request):
    """Delete artist from library."""
    def do_deletion():
      artist = model.ArtistInfo.get(request.artist_id)
      if artist:
        db.delete(model.Info.all(keys_only=True).ancestor(artist))
        return True
      else:
        return False
    return DeleteArtistResponse(
      artist_deleted = db.run_in_transaction(do_deletion))

  @remote.method(FetchArtistRequest, FetchArtistResponse)
  def fetch_artist(self, request):
    """Fetch artist from library."""
    artist_model = model.ArtistInfo.get(request.artist_id)
    if isinstance(artist_model, model.ArtistInfo):
      artist = self.__artist_from_model(artist_model)
    else:
      artist = None
    return FetchArtistResponse(artist=artist)


  @remote.method(SearchArtistsRequest, SearchArtistsResponse)
  def search_artists(self, request):
    """Search library for artists."""
    results, continuation = self.__search_info(request,
                                               model.ArtistInfo,
                                               self.__artist_from_model)
    return SearchArtistsResponse(artists=results or [],
                                 continuation=continuation or None)

  @remote.method(AddAlbumRequest, AddAlbumResponse)
  def add_album(self, request):
    """Add album to library."""
    def create_album():
      if not request.artist_id:
        raise ValueError('Request does not have artist-id.')
      artist = model.ArtistInfo.get(request.artist_id)
      if not artist:
        raise ValueError('No artist found for %s.' % request.artist_id)
      artist.album_count += 1
      artist.put()

      album = model.AlbumInfo(name=request.name,
                              released=request.released,
                              artist=artist,
                              parent=artist)
      album.put()

      return album
    album = db.run_in_transaction(create_album)

    return AddAlbumResponse(album_id=unicode(album.key()))

  @remote.method(UpdateAlbumRequest, UpdateAlbumResponse)
  def update_album(self, request):
    """Update album from library."""
    def do_deletion():
      album = model.AlbumInfo.get(request.album.album_id)
      if album:
        album.name = request.album.name
        album.released = request.album.released
        album.put()
        return True
      else:
        return False
    return UpdateAlbumResponse(album_updated=db.run_in_transaction(do_deletion))

  @remote.method(DeleteAlbumRequest, DeleteAlbumResponse)
  def delete_album(self, request):
    """Delete album from library."""
    def do_deletion():
      album = model.AlbumInfo.get(request.album_id)

      artist = album.artist
      artist.album_count -= 1
      artist.put()

      if album:
        db.delete(model.Info.all(keys_only=True).ancestor(album))
        return True
      else:
        return False

    return DeleteAlbumResponse(album_deleted=db.run_in_transaction(do_deletion))

  @remote.method(FetchAlbumRequest, FetchAlbumResponse)
  def fetch_album(self, request):
    """Fetch album from library."""
    album_model = model.AlbumInfo.get(request.album_id)
    if isinstance(album_model, model.AlbumInfo):
      album = self.__album_from_model(album_model)
    else:
      album = None
    return FetchAlbumResponse(album=album)

  @remote.method(SearchAlbumsRequest, SearchAlbumsResponse)
  def search_albums(self, request):
    """Search library for albums."""
    def customize_query(request, query):
      if request.artist_id:
        query.filter('artist', db.Key(request.artist_id))

    response = SearchAlbumsResponse()
    results, continuation = self.__search_info(request,
                                               model.AlbumInfo,
                                               self.__album_from_model,
                                               customize_query)
    return SearchAlbumsResponse(albums=results or [],
                                continuation=continuation or None)
