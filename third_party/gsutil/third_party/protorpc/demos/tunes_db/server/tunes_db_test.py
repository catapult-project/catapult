#!/usr/bin/python2.4
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Tests for google3.apphosting.demos.tunes_db.server.tunes_db."""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import unittest

from protorpc import message_types
from protorpc import descriptor

import datastore_test_util
import model
import tunes_db


class MusicLibraryServiceTest(datastore_test_util.DatastoreTest):
  """Music library service tests."""

  def setUp(self):
    """Set up music library."""
    super(MusicLibraryServiceTest, self).setUp()

    self.service = tunes_db.MusicLibraryService()

    # Create a bunch of artists.
    #
    # Definitions are not defined in order to test that search order is
    # correct.
    self.aem = model.ArtistInfo(name='Amadou et Miriam')
    self.aem.put()

    self.abba = model.ArtistInfo(name='Abba')
    self.abba.put()

    self.furnaces = model.ArtistInfo(name='The Fiery Furnaces')
    self.furnaces.put()

    self.go_team = model.ArtistInfo(name='  The Go! Team  ')
    self.go_team.put()

    self.wendy_carlos = model.ArtistInfo(name='Wendy Carlos')
    self.wendy_carlos.put()

    self.beatles = model.ArtistInfo(name='The Beatles')
    self.beatles.put()

    # Albums.

    # The Go! Team.
    self.get_it_together = model.AlbumInfo(name='Get It Together',
                                           released=2000,
                                           artist=self.go_team,
                                           parent=self.go_team)
    self.get_it_together.put()

    self.thunder_lightening_strike = model.AlbumInfo(
        name='Thunder, Lightning, Strike',
        released=2004,
        artist=self.go_team,
        parent=self.go_team)
    self.thunder_lightening_strike.put()

    self.proof_of_youth = model.AlbumInfo(name='Proof of Youth',
                                          released=2007,
                                          artist=self.go_team,
                                          parent=self.go_team)
    self.proof_of_youth.put()

    # The Beatles.
    self.help = model.AlbumInfo(name='Help',
                                released=1965,
                                artist=self.beatles,
                                parent=self.beatles)
    self.help.put()

    self.yellow_submarine = model.AlbumInfo(name='Yellow Submarine',
                                            released=1969,
                                            artist=self.beatles,
                                            parent=self.beatles)
    self.yellow_submarine.put()

  def AssertArtistMatches(self, model_instance, message):
    """Helper function to assert that artist message matches a model instance.

    Args:
      model_instance: Datastore model instance of artist to check against.
      message: Artist message to check match for.
    """
    self.assertEquals(str(model_instance.key()), message.artist_id)
    self.assertEquals(str(model_instance.name), message.name)

  def AssertAlbumMatches(self, model_instance, message):
    """Helper function to assert that album message matches a model instance.

    Args:
      model_instance: Datastore model instance of album to check against.
      message: Album message to check match for.
    """
    self.assertEquals(model_instance.name, message.name)
    self.assertEquals(str(model_instance.key()), message.album_id)
    self.assertEquals(model_instance.released, message.released)
    self.assertEquals(str(model_instance.artist.key()), message.artist_id)

  def testAddArtist(self):
    """Test the add_artist remote method."""
    request = tunes_db.AddArtistRequest()
    request.name = 'Elvis Costello'

    response = self.service.add_artist(request)
    response.check_initialized()

    elvis = model.ArtistInfo.get(response.artist_id)
    self.assertEquals('Elvis Costello', elvis.name)

  def testUpdateArtist(self):
    """Test updating artist."""
    artist = tunes_db.Artist()
    artist.artist_id = str(self.wendy_carlos.key())
    artist.name = u'Walter Carlos'
    request = tunes_db.UpdateArtistRequest()
    request.artist = artist

    response = self.service.update_artist(request)
    response.check_initialized()

    self.assertTrue(response.artist_updated)
    walter_carlos = model.ArtistInfo.get(self.wendy_carlos.key())
    self.assertEquals(u'Walter Carlos', walter_carlos.name)

  def testUpdateArtist_NotFound(self):
    """Test updating artist when artist no longer exists."""
    wendy_carlos_key = self.wendy_carlos.key()
    self.wendy_carlos.delete()

    artist = tunes_db.Artist()
    artist.artist_id = str(wendy_carlos_key)
    artist.name = u'Walter Carlos'
    request = tunes_db.UpdateArtistRequest()
    request.artist = artist

    response = self.service.update_artist(request)
    response.check_initialized()

    self.assertFalse(response.artist_updated)
    self.assertEquals(None, model.ArtistInfo.get(wendy_carlos_key))

  def testDeleteArtist(self):
    """Test the delete_artist remote method."""
    request = tunes_db.DeleteArtistRequest()
    request.artist_id = str(self.go_team.key())

    response = self.service.delete_artist(request)
    response.check_initialized()
    self.assertEquals(True, response.artist_deleted)

    self.assertEquals(None, model.AlbumInfo.get(self.go_team.key()))
    self.assertEquals(None,
                      model.AlbumInfo.gql('WHERE artist = :1',
                                          self.go_team.key()).get())

    response = self.service.delete_artist(request)
    self.assertEquals(False, response.artist_deleted)

  def testFetchArtist(self):
    """Test the fetch_artist remote method."""
    request = tunes_db.FetchArtistRequest()
    request.artist_id = str(self.wendy_carlos.key())

    response = self.service.fetch_artist(request)
    response.check_initialized()

    self.AssertArtistMatches(self.wendy_carlos, response.artist)

  def testSearchArtist_NothingFound(self):
    """Test the search_artists remote method when no artists are found."""
    request = tunes_db.SearchArtistsRequest()
    request.name_prefix = u'Duke'

    response = self.service.search_artists(request)
    response.check_initialized()
    self.assertFalse(hasattr(response, 'artist_count'))

  def testSearchArtist_All(self):
    """Test searching all artists in the music library."""
    request = tunes_db.SearchArtistsRequest()
    request.fetch_size = 3

    response = self.service.search_artists(request)
    response.check_initialized()

    self.assertEquals(3, len(response.artists))
    self.AssertArtistMatches(self.abba, response.artists[0])
    self.AssertArtistMatches(self.aem, response.artists[1])
    self.AssertArtistMatches(self.beatles, response.artists[2])

    request = tunes_db.SearchArtistsRequest()
    request.continuation = response.continuation
    request.fetch_size = 3
    response = self.service.search_artists(request)
    response.check_initialized()

    self.assertEquals(3, len(response.artists))
    self.AssertArtistMatches(self.furnaces, response.artists[0])
    self.AssertArtistMatches(self.go_team, response.artists[1])
    self.AssertArtistMatches(self.wendy_carlos, response.artists[2])

    request = tunes_db.SearchArtistsRequest()
    request.continuation = response.continuation
    response = self.service.search_artists(request)
    response.check_initialized()

    self.assertEquals([], response.artists)

  def testSearchArtist_NamePrefix(self):
    """Test searching artists and matching by name prefix."""
    request = tunes_db.SearchArtistsRequest()
    request.name_prefix = u' { tHe!  '
    request.fetch_size = 2

    response = self.service.search_artists(request)
    response.check_initialized()

    self.assertEquals(2, len(response.artists))
    self.AssertArtistMatches(self.beatles, response.artists[0])
    self.AssertArtistMatches(self.furnaces, response.artists[1])

    request = tunes_db.SearchArtistsRequest()
    request.continuation = response.continuation

    response = self.service.search_artists(request)
    response.check_initialized()

    self.assertEquals(1, len(response.artists))
    self.assertEquals(None, response.continuation)
    self.AssertArtistMatches(self.go_team, response.artists[0])

  def testAddAlbum(self):
    """Test creating an album."""
    request = tunes_db.AddAlbumRequest()
    request.artist_id = str(self.furnaces.key())
    request.name = u'Blueberry Boat'
    request.released = 2004

    response = self.service.add_album(request)
    response.check_initialized()

    blueberry = model.AlbumInfo.get(response.album_id)
    self.assertEquals(self.furnaces.key(), blueberry.artist.key())
    self.assertEquals('Blueberry Boat', blueberry.name)
    self.assertEquals(2004, blueberry.released)

  def testUpdateAlbum(self):
    """Test updating album."""
    album = tunes_db.Album()
    album.album_id = str(self.proof_of_youth.key())
    album.name = u'Proof of Age'
    album.released = 1908
    request = tunes_db.UpdateAlbumRequest()
    request.album = album

    response = self.service.update_album(request)
    response.check_initialized()

    self.assertTrue(response.album_updated)
    proof_of_age = model.AlbumInfo.get(self.proof_of_youth.key())
    self.assertEquals(u'Proof of Age', proof_of_age.name)
    self.assertEquals(1908, proof_of_age.released)

  def testUpdateAlbum_NotFound(self):
    """Test updating album when album no longer exists."""
    proof_of_youth_key = self.proof_of_youth.key()
    self.proof_of_youth.delete()

    album = tunes_db.Album()
    album.album_id = str(proof_of_youth_key)
    album.name = u'Proof of Age'
    album.released = 1908
    request = tunes_db.UpdateAlbumRequest()
    request.album = album

    response = self.service.update_album(request)
    response.check_initialized()

    self.assertFalse(response.album_updated)
    self.assertEquals(None, model.AlbumInfo.get(proof_of_youth_key))

  def testSearchAlbum_All(self):
    """Test searching all albums in library."""
    request = tunes_db.SearchAlbumsRequest()
    request.fetch_size = 2

    response = self.service.search_albums(request)
    response.check_initialized()

    self.assertEquals(2, len(response.albums))
    self.AssertAlbumMatches(self.get_it_together, response.albums[0])
    self.AssertAlbumMatches(self.help, response.albums[1])

    request = tunes_db.SearchAlbumsRequest()
    request.continuation = response.continuation

    response = self.service.search_albums(request)
    response.check_initialized()

    self.assertEquals(2, len(response.albums))
    self.AssertAlbumMatches(self.proof_of_youth, response.albums[0])
    self.AssertAlbumMatches(self.thunder_lightening_strike, response.albums[1])

    request = tunes_db.SearchAlbumsRequest()
    request.continuation = response.continuation

    response = self.service.search_albums(request)
    response.check_initialized()
    self.assertEquals(1, len(response.albums))
    self.assertEquals(None, response.continuation)
    self.AssertAlbumMatches(self.yellow_submarine, response.albums[0])

  def testSearchAlbum_FilterArtist(self):
    """Test searching albums for specific artist in library."""
    request = tunes_db.SearchAlbumsRequest()
    request.fetch_size = 2
    request.artist_id = unicode(self.go_team.key())

    response = self.service.search_albums(request)
    response.check_initialized()

    self.assertEquals(2, len(response.albums))
    self.AssertAlbumMatches(self.get_it_together, response.albums[0])
    self.AssertAlbumMatches(self.proof_of_youth, response.albums[1])

    request = tunes_db.SearchAlbumsRequest()
    request.continuation = response.continuation

    response = self.service.search_albums(request)
    response.check_initialized()

    self.assertEquals(1, len(response.albums))
    self.assertEquals(None, response.continuation)
    self.AssertAlbumMatches(self.thunder_lightening_strike, response.albums[0])


if __name__ == '__main__':
  unittest.main()
