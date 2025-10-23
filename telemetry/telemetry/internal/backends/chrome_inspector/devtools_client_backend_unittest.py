# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from telemetry import decorators
from telemetry.testing import browser_test_case


def filterContexts(contexts):
  # Whether this omnibox context exists depends on browser feature state. To
  # make these tests pass regardless of browser feature state, filter out the
  # omnibox context. When the feature launches or becomes universally enabled,
  # this filtering can be removed.
  return [
      c for c in contexts if c['url'] != 'chrome://omnibox-popup.top-chrome/'
  ]


class DevToolsClientBackendTest(browser_test_case.BrowserTestCase):
  @property
  def _browser_backend(self):
    return self._browser._browser_backend

  @property
  def _devtools_client(self):
    return self._browser_backend.devtools_client

  def testGetChromeMajorNumber(self):
    major_num = self._devtools_client.GetChromeMajorNumber()
    self.assertIsInstance(major_num, int)
    self.assertGreater(major_num, 0)

  def testIsAlive(self):
    self.assertTrue(self._devtools_client.IsAlive())

  # https://github.com/catapult-project/catapult/issues/3099 (Android)
  # crbug.com/483212 (CrOS)
  @decorators.Enabled('has tabs')
  @decorators.Disabled('android', 'chromeos')
  def testGetUpdatedInspectableContexts(self):
    self._browser.tabs.New()
    c1 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts1 = filterContexts(c1.contexts)
    self.assertEqual(len(contexts1), 2)
    backends1 = [c1.GetInspectorBackend(c['id']) for c in contexts1]
    tabs1 = list(self._browser.tabs)

    c2 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts2 = filterContexts(c2.contexts)
    self.assertEqual(len(contexts2), 2)
    backends2 = [c2.GetInspectorBackend(c['id']) for c in contexts2]
    tabs2 = list(self._browser.tabs)
    self.assertEqual(backends2, backends1)
    self.assertEqual(tabs2, tabs1)

    self._browser.tabs.New()
    c3 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts3 = filterContexts(c3.contexts)
    self.assertEqual(len(contexts3), 3)
    backends3 = [c3.GetInspectorBackend(c['id']) for c in contexts3]
    tabs3 = list(self._browser.tabs)
    self.assertEqual(backends3[1], backends1[0])
    self.assertEqual(backends3[2], backends1[1])
    self.assertEqual(tabs3[0], tabs1[0])
    self.assertEqual(tabs3[1], tabs1[1])

    self._browser.tabs[1].Close()
    c4 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts4 = filterContexts(c4.contexts)
    self.assertEqual(len(contexts4), 2)
    backends4 = [c4.GetInspectorBackend(c['id']) for c in contexts4]
    tabs4 = list(self._browser.tabs)
    self.assertEqual(backends4[0], backends3[0])
    self.assertEqual(backends4[1], backends3[1])
    self.assertEqual(tabs4[0], tabs3[0])
    self.assertEqual(tabs4[1], tabs3[2])

  # https://github.com/catapult-project/catapult/issues/3099 (Android)
  # crbug.com/483212 (CrOS)
  @decorators.Disabled('android', 'chromeos')
  def testGetUpdatedInspectableContextsUpdateContextsData(self):
    c1 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts1 = filterContexts(c1.contexts)
    self.assertEqual(len(contexts1), 1)
    self.assertEqual(contexts1[0]['url'], 'about:blank')

    context_id = contexts1[0]['id']
    backend = c1.GetInspectorBackend(context_id)
    backend.Navigate(self.UrlOfUnittestFile('blank.html'), None, 10)
    c2 = self._devtools_client.GetUpdatedInspectableContexts()
    contexts2 = filterContexts(c2.contexts)
    self.assertEqual(len(contexts2), 1)
    self.assertTrue('blank.html' in contexts2[0]['url'])
    self.assertEqual(c2.GetInspectorBackend(context_id), backend)
