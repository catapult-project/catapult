/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  const LEVEL_OF_DETAIL = Object.freeze({
    XY: 'XY',
    ALERTS: 'ALERTS',
    ANNOTATIONS: 'ANNOTATIONS',
    HISTOGRAMS: 'HISTOGRAMS',
  });

  function getColumnsByLevelOfDetail(levelOfDetail, statistic) {
    switch (levelOfDetail) {
      case LEVEL_OF_DETAIL.XY:
        return new Set(['revision', 'timestamp', statistic, 'count']);
      case LEVEL_OF_DETAIL.ALERTS:
        return new Set(['revision', 'alert']);
      case LEVEL_OF_DETAIL.ANNOTATIONS:
        return new Set([
          ...getColumnsByLevelOfDetail(LEVEL_OF_DETAIL.XY, statistic),
          ...getColumnsByLevelOfDetail(LEVEL_OF_DETAIL.ALERTS, statistic),
          'diagnostics', 'revisions',
        ]);
      case LEVEL_OF_DETAIL.HISTOGRAMS:
        return new Set(['revision', 'histogram']);
      default:
        throw new Error(`${levelOfDetail} is not a valid Level Of Detail`);
    }
  }

  function transformDatum(datum, unit, conversionFactor) {
    datum.timestamp = new Date(datum.timestamp);

    datum.unit = unit;
    if (datum.avg) datum.avg *= conversionFactor;
    if (datum.std) datum.std *= conversionFactor;
    if (datum.sum) datum.sum *= conversionFactor;

    if (datum.diagnostics) {
      datum.diagnostics = tr.v.d.DiagnosticMap.fromDict(datum.diagnostics);
    }
    if (datum.histogram) {
      datum.histogram = tr.v.Histogram.fromDict(datum.histogram);
    }
    return datum;
  }

  class TimeseriesRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.method_ = 'POST';
      this.body_ = new FormData();
      this.body_.set('test_suite', options.testSuite);
      this.body_.set('measurement', options.measurement);
      this.body_.set('bot', options.bot);
      if (options.testCase) this.body_.set('test_case', options.testCase);

      this.statistic_ = options.statistic || 'avg';
      if (options.statistic) {
        this.body_.set('statistic', options.statistic);
      }

      if (options.buildType) this.body_.set('build_type', options.buildType);

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
      return '/api/timeseries2';
    }

    postProcess_(response) {
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
      return response.data.map(row => transformDatum(
          cp.normalize(this.columns_, row), unit, conversionFactor));
    }
  }

  return {
    getColumnsByLevelOfDetail,
    LEVEL_OF_DETAIL,
    TimeseriesRequest,
  };
});
