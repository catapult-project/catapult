# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core import util
from telemetry.core.backends.chrome import inspector_network
from telemetry.core.timeline import recording_options
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

  def testHTTPResponseTimelineRecorder(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    tests = {
        'blank.html': InspectorNetworkTabTest.TestCase(),
        'green_rect.html': InspectorNetworkTabTest.TestCase(
            monitoring=True, responses_count=1),
        'image_decoding.html': InspectorNetworkTabTest.TestCase(
            monitoring=True, responses_count=2, subresources=['image.png']),
        }
    for page, test in tests.iteritems():
      opts = recording_options.TimelineRecordingOptions()
      if test.monitoring:
        opts.record_network = True
      self._tab.StartTimelineRecording(opts)
      self._tab.Navigate(self._browser.http_server.UrlOf(page))
      self._tab.WaitForDocumentReadyStateToBeComplete()
      self._tab.StopTimelineRecording()

      self.assertTrue(self._tab.timeline_model)
      events = self._tab.timeline_model.GetAllEventsOfName('HTTPResponse')
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
          self.assertEqual(False, base64_encoded)
        else:
          # We know this is the only subresource type in our setup.
          self.assertEqual(resp.GetHeader('Content-Type'), 'image/png')
          self.assertFalse('<!DOCTYPE HTML>' in body)
          self.assertEqual(True, base64_encoded)
