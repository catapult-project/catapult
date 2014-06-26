# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core.backends.chrome import inspector_network
from telemetry.timeline import recording_options
from telemetry.unittest import tab_test_case


class InspectorNetworkTabTest(tab_test_case.TabTestCase):
  class TestCase(object):
    def __init__(self, monitoring = False, responses_count = 0,
                 subresources = None):
      # Whether to monitor network for this case.
      self.monitoring = monitoring
      # Number of responses expected for this case.
      self.responses_count = responses_count
      # List of subresource links for this case.
      self.subresources = subresources

  def __init__(self, *args):
    super(InspectorNetworkTabTest, self).__init__(*args)

  def _NavigateAndGetHTTPResponseEvents(self, page, record_network=True):
    opts = recording_options.TimelineRecordingOptions()
    opts.record_network = record_network
    self._tab.StartTimelineRecording(opts)
    self.Navigate(page)
    self._tab.StopTimelineRecording()

    self.assertTrue(self._tab.timeline_model)
    return self._tab.timeline_model.GetAllEventsOfName('HTTPResponse')

  def testHTTPResponseTimelineRecorder(self):
    tests = {
        'blank.html': InspectorNetworkTabTest.TestCase(),
        'green_rect.html': InspectorNetworkTabTest.TestCase(
            monitoring=True, responses_count=1),
        'image_decoding.html': InspectorNetworkTabTest.TestCase(
            monitoring=True, responses_count=2, subresources=['image.png']),
        }
    for page, test in tests.iteritems():
      events = self._NavigateAndGetHTTPResponseEvents(page, test.monitoring)
      self.assertEqual(test.responses_count, len(events))
      if not test.monitoring:
        continue

      # Verify required event fields
      for event in events:
        self.assertEqual('HTTPResponse', event.name)
        resp = inspector_network.InspectorNetworkResponseData.FromTimelineEvent(
            event)
        self.assertLess(0.0, resp.timestamp)

        self.assertTrue(resp.headers)
        self.assertTrue(resp.headers['Content-Length'])
        body, base64_encoded = resp.GetBody()

        link = resp.url[resp.url.rfind('/') + 1 :]
        self.assertTrue(link == page or link in test.subresources)
        if link == page:
          self.assertEqual(resp.GetHeader('Content-Type'), 'text/html')
          self.assertTrue('<!DOCTYPE HTML>' in body)
          self.assertFalse(base64_encoded)
        else:
          # We know this is the only subresource type in our setup.
          self.assertEqual(resp.GetHeader('Content-Type'), 'image/png')
          self.assertFalse('<!DOCTYPE HTML>' in body)
          self.assertTrue(base64_encoded)

  def testCacheableHTTPResponse(self):
    # We know this page has one PNG image and its cacheable.
    events = self._NavigateAndGetHTTPResponseEvents('image_decoding.html')
    images_first = []
    for event in events:
      resp = inspector_network.InspectorNetworkResponseData.FromTimelineEvent(
          event)
      if resp.GetHeader('Content-Type') == 'image/png':
        images_first.append(resp)

    self.assertEqual(1, len(images_first))
    self.assertFalse(images_first[0].served_from_cache)

    events = self._NavigateAndGetHTTPResponseEvents('image_decoding.html')
    images_second = []
    for event in events:
      resp = inspector_network.InspectorNetworkResponseData.FromTimelineEvent(
          event)
      if resp.GetHeader('Content-Type') == 'image/png':
        images_second.append(resp)
    self.assertEqual(1, len(images_second))
    # On the second fetch, the image is served from cache.
    self.assertTrue(images_second[0].served_from_cache)
