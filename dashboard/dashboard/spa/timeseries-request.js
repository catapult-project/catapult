/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';
import {normalize, transformAlert} from './utils.js';

export const LEVEL_OF_DETAIL = Object.freeze({
  XY: 'XY',
  ALERTS: 'ALERTS',
  ANNOTATIONS: 'ANNOTATIONS',
  DETAILS: 'DETAILS',
});

const DETAILS_COLUMNS = new Set([
  'revision',
  'timestamp',
  'avg', 'std', 'count',  // TODO other statistics
  'revisions',
  'annotations',
  'alert',
  // TODO Uncomment when ready to display these:
  // 'diagnostics',
  // 'histogram',
]);

export function getColumnsByLevelOfDetail(levelOfDetail, statistic) {
  switch (levelOfDetail) {
    case LEVEL_OF_DETAIL.XY:
      return new Set(['revision', statistic]);
    case LEVEL_OF_DETAIL.ALERTS:
      return new Set(['revision', 'alert']);
    case LEVEL_OF_DETAIL.ANNOTATIONS:
      return new Set([
        ...getColumnsByLevelOfDetail(LEVEL_OF_DETAIL.XY, statistic),
        'timestamp', 'count',
        ...getColumnsByLevelOfDetail(LEVEL_OF_DETAIL.ALERTS, statistic),
        'diagnostics', 'revisions',
      ].sort());
    case LEVEL_OF_DETAIL.DETAILS:
      return DETAILS_COLUMNS;
    default:
      throw new Error(`${levelOfDetail} is not a valid Level Of Detail`);
  }
}

function transformDatum(datum, unit, conversionFactor) {
  if (datum.timestamp) datum.timestamp = new Date(datum.timestamp);

  datum.unit = unit;
  if (!datum.count) datum.count = 1;
  if (datum.avg) datum.avg *= conversionFactor;
  if (datum.std) datum.std *= conversionFactor;
  if (datum.sum) datum.sum *= conversionFactor;

  if (datum.alert) datum.alert = transformAlert(datum.alert);
  if (datum.diagnostics) {
    datum.diagnostics = tr.v.d.DiagnosticMap.fromDict(datum.diagnostics);
  }
  if (datum.histogram) {
    datum.histogram = tr.v.Histogram.fromDict(datum.histogram);
  }
  return datum;
}

export class TimeseriesRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.method_ = 'POST';
    this.body_ = new FormData();
    this.body_.set('test_suite', options.suite);
    this.body_.set('measurement', options.measurement);
    this.body_.set('bot', options.bot);
    if (options.case) this.body_.set('test_case', options.case);

    this.statistic_ = options.statistic || 'avg';
    if (options.statistic) {
      this.body_.set('statistic', options.statistic);
    }

    this.body_.set('build_type', options.buildType || 'test');

    this.columns_ = [...getColumnsByLevelOfDetail(
        options.levelOfDetail, this.statistic_)];
    this.body_.set('columns', this.columns_.join(','));

    if (options.minRevision) {
      this.body_.set('min_revision', options.minRevision);
    }
    if (options.maxRevision) {
      this.body_.set('max_revision', options.maxRevision);
    }
  }

  get url_() {
    return TimeseriesRequest.URL;
  }

  get description_() {
    return 'loading timeseries for ' + [
      this.body_.get('test_suite'),
      this.body_.get('measurement'),
      this.body_.get('bot'),
      this.body_.get('test_case') || '',
    ].join('/');
  }

  postProcess_(response, isFromChannel = false) {
    if (!response) return;
    let unit = tr.b.Unit.byJSONName[response.units];
    let conversionFactor = 1;
    if (!unit) {
      const info = tr.v.LEGACY_UNIT_INFO.get(response.units);
      if (info) {
        conversionFactor = info.conversionFactor || 1;
        unit = tr.b.Unit.byName[info.name];
      } else {
        unit = tr.b.Unit.byName.unitlessNumber;
      }
    }

    // The backend returns denormalized (tabular) data, but
    // TimeseriesCacheRequest yields normalized (objects) data for speed.
    // Rely on TimeseriesCacheRequest to merge data from network requests in
    // with previous data, so this code does not need to worry about merging
    // across levels of detail.
    return response.data.map(row => transformDatum(
        (isFromChannel ? row : normalize(this.columns_, row)),
        unit, conversionFactor));
  }
}

TimeseriesRequest.URL = '/api/timeseries2';
