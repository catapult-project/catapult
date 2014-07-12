# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import StringIO
import unittest

from telemetry.page import page_set
from telemetry.results import html_page_measurement_results
from telemetry.value import scalar


def _MakePageSet():
  ps = page_set.PageSet(file_path=os.path.dirname(__file__))
  ps.AddPageWithDefaultRunNavigate('http://www.foo.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.bar.com/')
  ps.AddPageWithDefaultRunNavigate('http://www.baz.com/')
  return ps


class DeterministicHtmlPageMeasurementResults(
    html_page_measurement_results.HtmlPageMeasurementResults):
  def _GetBuildTime(self):
    return 'build_time'

  def _GetRevision(self):
    return 'revision'


# Wrap string IO with a .name property so that it behaves more like a file.
class StringIOFile(StringIO.StringIO):
  name = 'fake_output_file'


class HtmlPageMeasurementResultsTest(unittest.TestCase):

  def test_basic_summary(self):
    test_page_set = _MakePageSet()
    output_file = StringIOFile()

    # Run the first time and verify the results are written to the HTML file.
    results = DeterministicHtmlPageMeasurementResults(
        output_file, 'test_name', False, False, 'browser_type')
    results.WillMeasurePage(test_page_set.pages[0])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[0], 'a', 'seconds', 3))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[0])

    results.WillMeasurePage(test_page_set.pages[1])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[1], 'a', 'seconds', 7))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[1])

    results.PrintSummary()
    results.GetResults()
    expected = {
      "platform": "browser_type",
      "buildTime": "build_time",
      "label": None,
      "tests": {
        "test_name": {
          "metrics": {
            "a": {
              "current": [3, 7],
              "units": "seconds",
              "important": True
            },
            "telemetry_page_measurement_results.num_failed": {
              "current": [0],
              "units": "count",
              "important": False
            },
            "a.http://www.bar.com/": {
              "current": [7],
              "units": "seconds",
              "important": False
            },
            "telemetry_page_measurement_results.num_errored": {
              "current": [0],
              "units": "count",
              "important": False
            },
            "a.http://www.foo.com/": {
              "current": [3],
              "units": "seconds",
              "important": False
            }
          }
        }
      },
      "revision": "revision"
    }
    self.assertEquals(expected, results.GetResults())

    # Run the second time and verify the results are appended to the HTML file.
    output_file.seek(0)
    results = DeterministicHtmlPageMeasurementResults(
        output_file, 'test_name', False, False, 'browser_type')
    results.WillMeasurePage(test_page_set.pages[0])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[0], 'a', 'seconds', 4))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[0])

    results.WillMeasurePage(test_page_set.pages[1])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[1], 'a', 'seconds', 8))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[1])

    results.PrintSummary()
    expected = [
      {
        "platform": "browser_type",
        "buildTime": "build_time",
        "label": None,
        "tests": {
          "test_name": {
            "metrics": {
              "a": {
                "current": [3, 7],
                "units": "seconds",
                "important": True
              },
              "telemetry_page_measurement_results.num_failed": {
                "current": [0],
                "units": "count",
                "important": False
              },
              "a.http://www.bar.com/": {
                "current": [7],
                "units": "seconds",
                "important": False
              },
              "telemetry_page_measurement_results.num_errored": {
                "current": [0],
                "units": "count",
                "important": False
              },
              "a.http://www.foo.com/": {
                "current": [3],
                "units": "seconds",
                "important": False
              }
            }
          }
        },
        "revision": "revision"
      },
      {
        "platform": "browser_type",
        "buildTime": "build_time",
        "label": None,
        "tests": {
          "test_name": {
            "metrics": {
              "a": {
                "current": [4, 8],
                "units": "seconds",
                "important": True
              },
              "telemetry_page_measurement_results.num_failed": {
                "current": [0],
                "units": "count",
                "important": False,
              },
              "a.http://www.bar.com/": {
                "current": [8],
                "units": "seconds",
                "important": False
              },
              "telemetry_page_measurement_results.num_errored": {
                "current": [0],
                "units": "count",
                "important": False
              },
              "a.http://www.foo.com/": {
                "current": [4],
                "units": "seconds",
                "important": False
              }
            }
          }
        },
        "revision": "revision"
      }]
    self.assertEquals(expected, results.GetCombinedResults())
    last_output_len = len(output_file.getvalue())

    # Now reset the results and verify the old ones are gone.
    output_file.seek(0)
    results = DeterministicHtmlPageMeasurementResults(
       output_file, 'test_name', True, False, 'browser_type')
    results.WillMeasurePage(test_page_set.pages[0])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[0], 'a', 'seconds', 5))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[0])

    results.WillMeasurePage(test_page_set.pages[1])
    results.AddValue(scalar.ScalarValue(
        test_page_set.pages[1], 'a', 'seconds', 9))
    results.DidMeasurePage()
    results.AddSuccess(test_page_set.pages[1])

    results.PrintSummary()
    expected = [{
      "platform": "browser_type",
      "buildTime": "build_time",
      "label": None,
      "tests": {
        "test_name": {
          "metrics": {
            "a": {
              "current": [5, 9],
              "units": "seconds",
              "important": True
            },
            "telemetry_page_measurement_results.num_failed": {
              "current": [0],
              "units": "count",
              "important": False
            },
            "a.http://www.bar.com/": {
              "current": [9],
              "units": "seconds",
              "important": False
            },
            "telemetry_page_measurement_results.num_errored": {
              "current": [0],
              "units": "count",
              "important": False
            },
            "a.http://www.foo.com/": {
              "current": [5],
              "units": "seconds",
              "important": False
            }
          }
        }
      },
      "revision": "revision"
    }]
    self.assertEquals(expected, results.GetCombinedResults())
    self.assertTrue(len(output_file.getvalue()) < last_output_len)
