# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Converts from histogram.proto JSON to histogram JSON.

This code is here as a stepping stone between the new histogram.proto format
(introduced early 2020) and the older histogram set JSON format. The latter
format is described in docs/histogram-set-json-format.md. Therefore, this code
should be removed once histogram.py is capable of de-serializing from the proto
directly.
"""

import json
import logging

UNIT_MAP = {
    'MS': 'ms',
    'MS_BEST_FIT_FORMAT': 'msBestFitFormat',
    'TS_MS': 'tsMs',
    'N_PERCENT': 'n%',
    'SIZE_IN_BYTES': 'sizeInBytes',
    'BYTES_PER_SECOND': 'bytesPerSecond',
    'J': 'J',
    'W': 'W',
    'A': 'A',
    'V': 'V',
    'HERTZ': 'Hz',
    'UNITLESS': 'unitless',
    'COUNT': 'count',
    'SIGMA': 'sigma',
}

IMPROVEMENT_DIRECTION_MAP = {
    'BIGGER_IS_BETTER': 'biggerIsBetter',
    'SMALLER_IS_BETTER': 'smallerIsBetter',
}

BOUNDARY_TYPE_MAP = {
    'LINEAR': 0,
    'EXPONENTIAL': 1,
}


def ConvertHistogram(proto_dict):
  if not 'name' in proto_dict:
    raise ValueError('The "name" field is required.')

  hist = {
      'name': proto_dict['name'],
  }
  _ParseUnit(hist, proto_dict)
  _ParseDescription(hist, proto_dict)
  _ParseBinBounds(hist, proto_dict)
  _ParseDiagnostics(hist, proto_dict)
  _ParseSampleValues(hist, proto_dict)
  _ParseMaxSampleValues(hist, proto_dict)
  _ParseNumNans(hist, proto_dict)
  _ParseNanDiagnostics(hist, proto_dict)
  _ParseRunning(hist, proto_dict)
  _ParseAllBins(hist, proto_dict)
  _ParseSummaryOptions(hist, proto_dict)

  return hist


def ConvertSharedDiagnostics(shared_diagnostics):
  for guid, body in shared_diagnostics.items():
    diagnostic = _ConvertDiagnostic(body)
    diagnostic['guid'] = guid
    yield diagnostic


def _ParseUnit(hist, proto_dict):
  if not 'unit' in proto_dict:
    raise ValueError('The "unit" field is required.')

  improvement_direction = proto_dict['unit'].get('improvement_direction')
  unit = UNIT_MAP[proto_dict['unit']['unit']]
  hist['unit'] = unit
  if improvement_direction and improvement_direction != 'NOT_SPECIFIED':
    hist['unit'] += '_' + IMPROVEMENT_DIRECTION_MAP[improvement_direction]


def _ParseDescription(hist, proto_dict):
  description = proto_dict.get('description')
  if description:
    hist['description'] = description


def _ParseBinBounds(hist, proto_dict):
  bin_bounds = proto_dict.get('binBoundaries')
  if not bin_bounds:
    return

  first = bin_bounds['firstBinBoundary']
  hist['binBoundaries'] = [first]
  bin_specs = bin_bounds.get('binSpecs')
  if bin_specs:
    for spec in bin_specs:
      if 'binBoundary' in spec:
        value = int(spec['binBoundary'])
        hist['binBoundaries'].append(value)
      elif 'binSpec' in spec:
        detailed_spec = spec['binSpec']
        boundary_type = BOUNDARY_TYPE_MAP[detailed_spec['boundaryType']]
        maximum = int(detailed_spec['maximumBinBoundary'])
        num_boundaries = int(detailed_spec['numBinBoundaries'])
        hist['binBoundaries'].append([boundary_type, maximum, num_boundaries])


def _ParseDiagnostics(hist, proto_dict):
  diagnostics = proto_dict.get('diagnostics')
  if diagnostics:
    hist['diagnostics'] = {}
    for name, diag_json in diagnostics['diagnosticMap'].items():
      diagnostic = _ConvertDiagnostic(diag_json)
      hist['diagnostics'][name] = diagnostic


def _ParseSampleValues(hist, proto_dict):
  sample_values = proto_dict.get('sampleValues')
  if sample_values:
    hist['sampleValues'] = proto_dict['sampleValues']


def _ParseMaxSampleValues(hist, proto_dict):
  max_num_sample_values = proto_dict.get('maxNumSampleValues')
  if max_num_sample_values:
    hist['maxNumSampleValues'] = max_num_sample_values


def _ParseNumNans(hist, proto_dict):
  num_nans = proto_dict.get('numNans')
  if num_nans:
    hist['numNans'] = num_nans


def _ParseNanDiagnostics(_, proto_dict):
  nan_diagnostics = proto_dict.get('nanDiagnostics')
  if nan_diagnostics:
    raise TypeError('NaN diagnostics: Not implemented yet')


def _ParseRunning(hist, proto_dict):
  running = proto_dict.get('running')

  if running:
    def _SafeValue(key):
      return running.get(key, 0)

    hist['running'] = [
        _SafeValue('count'), _SafeValue('max'), _SafeValue('meanlogs'),
        _SafeValue('mean'), _SafeValue('min'), _SafeValue('sum'),
        _SafeValue('variance')
    ]


def _ParseAllBins(hist, proto_dict):
  all_bins = proto_dict.get('allBins')
  if not all_bins:
    return

  hist['allBins'] = {}
  for index_str, bin_spec in all_bins.items():
    bin_count = bin_spec['binCount']
    hist['allBins'][index_str] = [bin_count]
    bin_diagnostics = bin_spec.get('diagnosticMaps')
    if bin_diagnostics:
      dest_diagnostics = []
      for diag_map in bin_diagnostics:
        bin_diag_map = {}
        for name, diag_json in diag_map['diagnosticMap'].items():
          diagnostic = _ConvertDiagnostic(diag_json)
          bin_diag_map[name] = diagnostic
        dest_diagnostics.append(bin_diag_map)
      hist['allBins'][index_str].append(dest_diagnostics)


def _ParseSummaryOptions(hist, proto_dict):
  summary_options = proto_dict.get('summaryOptions')
  if summary_options:
    hist['summaryOptions'] = summary_options


def _ConvertDiagnostic(proto_dict):

  def _GetType(d):
    # The dict should be one key mapped to another dict, and the key is the
    # the type of the diagnostic. E.g. "genericSet": {...}.
    assert len(d) == 1, ('Expected diagnostic to be dict with just one key. '
                         'Was: %s' % proto_dict)
    return next(iter(d))

  diag_type = _GetType(proto_dict)
  if diag_type == 'genericSet':
    return _ConvertGenericSet(proto_dict)
  elif diag_type == 'sharedDiagnosticGuid':
    return proto_dict['sharedDiagnosticGuid']
  else:
    raise ValueError('%s not yet supported by proto-JSON' % diag_type)


def _ConvertGenericSet(proto_dict):
  # Values can be of any JSON type. Therefore, GenericSet values are kind of
  # double encoded - they're JSON-encoded data in a string inside of the
  # proto JSON format. Note that proto_dict is already JSON decoded, so we
  # just need to decode the values string here.
  values = []
  for value_json in proto_dict['genericSet']['values']:
    try:
      values.append(json.loads(value_json))
    except (TypeError, ValueError) as e:
      logging.exception(e)
      raise TypeError('The value %s is not valid JSON. You cannot pass naked '
                      'strings as a GenericSet value, for instance; they '
                      'have to be quoted. Therefore, 1234 is a valid value '
                      '(int), "abcd" is a valid value (string), but abcd is '
                      'not valid.' % value_json)

  return {
      'type': 'GenericSet',
      'values': values,
  }
