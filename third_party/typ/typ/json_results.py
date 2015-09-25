# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import OrderedDict

import json


class ResultType(object):
    Pass = 'Pass'
    Failure = 'Failure'
    ImageOnlyFailure = 'ImageOnlyFailure'
    Timeout = 'Timeout'
    Crash = 'Crash'
    Skip = 'Skip'

    values = (Pass, Failure, ImageOnlyFailure, Timeout, Crash, Skip)


class Result(object):
    # too many instance attributes  pylint: disable=R0902
    # too many arguments  pylint: disable=R0913

    def __init__(self, name, actual, started, took, worker,
                 expected=None, unexpected=False,
                 flaky=False, code=0, out='', err='', pid=0):
        self.name = name
        self.actual = actual
        self.started = started
        self.took = took
        self.worker = worker
        self.expected = expected or [ResultType.Pass]
        self.unexpected = unexpected
        self.flaky = flaky
        self.code = code
        self.out = out
        self.err = err
        self.pid = pid


class ResultSet(object):

    def __init__(self):
        self.results = []

    def add(self, result):
        self.results.append(result)


TEST_SEPARATOR = '.'


def make_full_results(metadata, seconds_since_epoch, all_test_names, results):
    """Convert the typ results to the Chromium JSON test result format.

    See http://www.chromium.org/developers/the-json-test-results-format
    """

    # We use OrderedDicts here so that the output is stable.
    full_results = OrderedDict()
    full_results['version'] = 3
    full_results['interrupted'] = False
    full_results['path_delimiter'] = TEST_SEPARATOR
    full_results['seconds_since_epoch'] = seconds_since_epoch

    for md in metadata:
        key, val = md.split('=', 1)
        full_results[key] = val

    passing_tests = _passing_test_names(results)
    failed_tests = failed_test_names(results)
    skipped_tests = set(all_test_names) - passing_tests - failed_tests

    full_results['num_failures_by_type'] = OrderedDict()
    full_results['num_failures_by_type']['FAIL'] = len(failed_tests)
    full_results['num_failures_by_type']['PASS'] = len(passing_tests)
    full_results['num_failures_by_type']['SKIP'] = len(skipped_tests)

    full_results['tests'] = OrderedDict()

    for test_name in all_test_names:
        value = OrderedDict()
        if test_name in skipped_tests:
            value['expected'] = 'SKIP'
            value['actual'] = 'SKIP'
        else:
            value['expected'] = 'PASS'
            value['actual'] = _actual_results_for_test(test_name, results)
            if value['actual'].endswith('FAIL'):
                value['is_unexpected'] = True
        _add_path_to_trie(full_results['tests'], test_name, value)

    return full_results


def make_upload_request(test_results_server, builder, master, testtype,
                        full_results):
    url = 'http://%s/testfile/upload' % test_results_server
    attrs = [('builder', builder),
             ('master', master),
             ('testtype', testtype)]
    content_type, data = _encode_multipart_form_data(attrs, full_results)
    return url, content_type, data


def exit_code_from_full_results(full_results):
    return 1 if num_failures(full_results) else 0


def num_failures(full_results):
    return full_results['num_failures_by_type']['FAIL']


def failed_test_names(results):
    names = set()
    for r in results.results:
        if r.actual == ResultType.Failure:
            names.add(r.name)
        elif r.actual == ResultType.Pass and r.name in names:
            names.remove(r.name)
    return names


def _passing_test_names(results):
    return set(r.name for r in results.results if r.actual == ResultType.Pass)


def _actual_results_for_test(test_name, results):
    actuals = []
    for r in results.results:
        if r.name == test_name:
            if r.actual == ResultType.Failure:
                actuals.append('FAIL')
            elif r.actual == ResultType.Pass:
                actuals.append('PASS')

    assert actuals, 'We did not find any result data for %s.' % test_name
    return ' '.join(actuals)


def _add_path_to_trie(trie, path, value):
    if TEST_SEPARATOR not in path:
        trie[path] = value
        return
    directory, rest = path.split(TEST_SEPARATOR, 1)
    if directory not in trie:
        trie[directory] = {}
    _add_path_to_trie(trie[directory], rest, value)


def _encode_multipart_form_data(attrs, test_results):
    # Cloned from webkitpy/common/net/file_uploader.py
    BOUNDARY = '-J-S-O-N-R-E-S-U-L-T-S---B-O-U-N-D-A-R-Y-'
    CRLF = '\r\n'
    lines = []

    for key, value in attrs:
        lines.append('--' + BOUNDARY)
        lines.append('Content-Disposition: form-data; name="%s"' % key)
        lines.append('')
        lines.append(value)

    lines.append('--' + BOUNDARY)
    lines.append('Content-Disposition: form-data; name="file"; '
                 'filename="full_results.json"')
    lines.append('Content-Type: application/json')
    lines.append('')
    lines.append(json.dumps(test_results))

    lines.append('--' + BOUNDARY + '--')
    lines.append('')
    body = CRLF.join(lines)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body
