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

"""Tunes DB user interface.

This demonstrates how to use the Service API to connect to a service via
another web-app.
"""

import appengine_config

import logging
import os
import urllib

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from protorpc import transport
import tunes_db

if os.environ['SERVER_SOFTWARE'].startswith('Development'):
  TUNES_DB_HOST = 'localhost:8082'
else:
  TUNES_DB_HOST = 'tunes-db.appspot.com'

TUNES_DB_URL = 'http://%s/music' % TUNES_DB_HOST
PAGE_SIZE = 10

music_service = tunes_db.MusicLibraryService.Stub(
  transport.HttpTransport(TUNES_DB_URL))


class MainHandler(webapp.RequestHandler):
  """Base handler for all handlers of the Tunes DB client.

  By default any call to get redirects to the Artists page.
  """

  def go(self, page, **kwargs):
    """Redirection that preserves basic search parameters.

    Args:
      page: Page to redirect to.
      kwargs: Additional parameters to add to query parameter of redirection.
    """
    kwargs.update({'s': self.request.params.get('s', ''),
                   'c': self.request.params.get('c', ''),
                  })
    params = dict((name, value) for name, value in kwargs.iteritems()
                   if value is not None)
    self.redirect('%s?%s' % (page, urllib.urlencode(params)))

  def get(self):
    """Redirect to Artists page."""
    self.go('/artists')


class ArtistsHandler(MainHandler):
  """Artists page handler."""

  def get(self):
    """Show Artists search page.

    Parameters:
      s: Search string.  Searches artist name prefix.
      c: Continuation if paginating.
    """
    search_string = self.request.get('s', '')
    continuation = self.request.get('c', '')
    if continuation:
      name_prefix = None
    else:
      name_prefix = search_string

    response = music_service.search_artists(fetch_size=PAGE_SIZE,
                                            continuation=continuation or None,
                                            name_prefix=name_prefix)

    self.response.out.write(
        template.render('artists.html',
                        {'artists': response.artists,
                         'search_string': search_string,

                         # Paging information.
                         'continuation': response.continuation or '',
                         'this_page': continuation,
                         'nav_action': '/artists',
                        },
                        True))


class UpdateArtistHandler(MainHandler):
  """Handler for updating artist information."""

  def post(self):
    """Update new artist."""
    artist_id = self.request.params['artist_id']
    artist = tunes_db.Artist(artist_id=artist_id,
                             name=self.request.params['artist_name'])
    response = music_service.update_artist(artist=artist)

    logging.info('Update artist %s success: %s',
                 artist_id,
                 response.artist_updated)

    if response.artist_updated:
      error_message = None
    else:
      error_message = 'Update artist failed.'

    self.go('/artist',
            artist_id=artist_id,
            error_message=error_message)


class ArtistActionHandler(MainHandler):
  """Handler for actions on artists."""

  def __delete_artists(self, artist_ids):
    """Delete artist action.

    Args:
      artist_ids: Iterable if artist ids to delete.
    """
    for artist_id in artist_ids:
      # TODO(rafek): Delete should support multi.
      response = music_service.delete_artist(artist_id=artist_id.encode('utf-8'))
      logging.info('Deleted artist %s: %s', artist_id, response.artist_deleted)

  def post(self):
    """General purpose action handler.

    Operates on a all artist ids provided by the artist_id parameters.

    Parameters:
      action: Action to perform.
        Delete: Delete artists.
      artist_id: Multi-parameter of artist ids to delete.
    """
    action = self.request.params['action']
    artist_ids = [a for a in self.request.get_all('artist_id')]

    action_map = {
        'Delete': self.__delete_artists,
        }

    action_map[action](artist_ids)

    self.go('/artists')


class ArtistHandler(MainHandler):
  """Handler for viewing and creating Artist."""

  def get(self):
    """Show Artist information and albums."""
    continuation = self.request.get('c', '')

    artist_id = self.request.params['artist_id'].encode('utf-8')
    artist = music_service.fetch_artist(artist_id=artist_id).artist

    if continuation:
      search_artist_id = None
    else:
      search_artist_id = artist_id

    response = music_service.search_albums(fetch_size=PAGE_SIZE,
                                           continuation=continuation or None,
                                           artist_id=search_artist_id)
    albums = response.albums

    customized_search = urllib.urlencode({'artist_id': artist_id})

    template_data = {'artist': artist,
                     'albums': albums,

                     # Paging information.
                     'continuation': response.continuation or '',
                     'this_page': continuation,
                     'nav_action': '/artist',
                     'customized_search': '&' + customized_search,
                    }

    error_message = self.request.get('error_message')
    if error_message:
      template_data['error_message'] = error_message

    self.response.out.write(
        template.render('artist.html', template_data, True))

  def post(self):
    """Post new artist.

    Parameters:
      artist_name: Name of new artist.
    """
    response = music_service.add_artist(name=self.request.params['artist_name'])
    logging.info('Created artist with id %s.', response.artist_id)

    self.go('/artists')


class AlbumsHandler(MainHandler):
  """Handler for search albums."""

  def get(self):
    """Show Albums search page.

    Parameters:
      s: Search string.  Searches artist name prefix.
      c: Continuation if paginating.
    """
    search_string = self.request.get('s', '')
    continuation = self.request.get('c', '')

    if continuation:
      name_prefix = None
    else:
      name_prefix = search_string

    response = music_service.search_albums(fetch_size=PAGE_SIZE,
                                           continuation=continuation or None,
                                           name_prefix=search_string)
    albums = response.albums

    self.response.out.write(
        template.render('albums.html',
                        {'albums': albums,
                         'search_string': search_string,

                         # Paging information.
                         'continuation': response.continuation or '',
                         'this_page': continuation,
                         'nav_action': '/albums',
                         },
                        True))


class AlbumHandler(MainHandler):
  """Handler for viewing and creating Albums."""

  def get(self):
    """Show Album information and albums."""
    album_id = self.request.params['album_id'].encode('utf-8')

    album = music_service.fetch_album(album_id=album_id).album

    artist = music_service.fetch_artist(artist_id=album.artist_id).artist

    self.response.out.write(
        template.render('album.html',
                        {'album': album,
                         'artist': artist,
                         },
                        True))

  def post(self):
    """Post a new Album to Tunes DB.

    Parameters:
      album_name: Name of new album.
      album_released: Release year of new album.
    """
    released = self.request.get('album_released', None)
    if released:
      released = int(released)
    else:
      # Might be empty string.
      released = None

    artist_id = self.request.params['album_artist_id'].encode('utf-8')
    response = music_service.add_album(
      name=self.request.params['album_name'],
      released=released,
      artist_id=artist_id)
    logging.info('Created album with id %s.', response.album_id)

    self.go('/artist', artist_id=artist_id)


class UpdateAlbumHandler(MainHandler):
  """Handler for editing and updating album information."""

  def post(self):
    """Update album."""
    album = music_service.fetch_album(
      album_id=str(self.request.params['album_id'])).album

    album.album_id = str(self.request.params['album_id'])
    album.name = self.request.params['album_name']
    released = self.request.get('album_released')
    if released:
      album.released = int(released)
    else:
      album.reset('released')

    response = music_service.update_album(album=album)
    album_updated = response.album_updated
    logging.info('Update album %s success: %s',
                 album.album_id,
                 response.album_updated)

    if album_updated:
      error_message = None
    else:
      error_message = 'Album was not updated.'

    self.go('/album', album_id=album.album_id, error_message=error_message)


class AlbumActionHandler(MainHandler):
  """Album action handler."""

  def __delete_albums(self, album_ids):
    """Delete album action.

    Args:
      album_ids: Iterable of album ids to delete.
    """
    for album_id in album_ids:
      # TODO(rafek): Delete should support multi.
      response = music_service.delete_album(album_id=album_id.encode('utf-8'))
      logging.info('Deleted album %s: %s', album_id, response.album_deleted)

  def post(self):
    """General purpose action handler.

    Operates on a all album ids provided by the album_id parameters.

    Parameters:
      action: Action to perform.
        Delete: Delete artists.
      artist_id: Multi-parameter of artist ids to delete.
    """
    action = self.request.params['action']
    artist_id = self.request.params['artist_id']
    album_ids = [a for a in self.request.get_all('album_id')]

    action_map = {
        'Delete': self.__delete_albums,
        }

    action_map[action](album_ids)

    self.go('/artist', artist_id=artist_id)


def main():
  application = webapp.WSGIApplication([('/', MainHandler),
                                        ('/artists', ArtistsHandler),
                                        ('/artist', ArtistHandler),
                                        ('/update_artist', UpdateArtistHandler),
                                        ('/artist_action', ArtistActionHandler),
                                        ('/albums', AlbumsHandler),
                                        ('/album', AlbumHandler),
                                        ('/update_album', UpdateAlbumHandler),
                                        ('/album_action', AlbumActionHandler),
                                       ],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
