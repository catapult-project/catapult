// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
"use strict";

export default (function() {
  const FLUSH_THRESHOLD_MS = 60 * 1000;

  // ValueType enum:
  const ValueType = Object.freeze({
    NON_CUMULATIVE_INT: 0,
    CUMULATIVE_INT: 1,
    NON_CUMULATIVE_FLOAT: 2,
    CUMULATIVE_FLOAT: 3,
    STRING: 4,
    BOOL: 5,
    NON_CUMULATIVE_DISTRIBUTION: 6,
    CUMULATIVE_DISTRIBUTION: 7
  });

  // FieldType enum:
  const FieldType = Object.freeze({
    STRING: 1, // These begin at 1 instead of 0. Shrug.
    INT: 2,
    BOOL: 3
  });

  /**
    TSMonClient is a client proxy for chrome-infra's ts_mon server libraries.
    Although it is possible to use this API directly, the intent is for
    servers to generate declarations for you, which you then include in
    your html.

    @example initialize the client
    let tsm = new TSMonClient();

    @example create a boolean metric.
    let boolTest = tsm.bool('frontend/bool_test');
    boolTest.set(true);

    @example create a counter metric, with some fields.
    const metricFields = new Map(Object.entries({
      "some_string": TSMonClient.stringField("some_string"),
      "some_bool": TSMonClient.boolField("some_bool"),
      "some_int": TSMonClient.intField("some_int"),
    }));
    const counterTest = tsm.counter('frontend/counter_test', 'test counter',
      null, metricFields);
    const measurementFields = new Map(Object.entries({
      "some_string": "foo",
      "some_bool": true,
      "some_int": 42,
    }));
    counterTest.add(1, fields);

    @example create a cumulative distribution metric.
    let cumulativeDistributionTest =
        tsm.counter('frontend/cumulativedistribution_test');
    cumulativeDistributionTest.add(1);

    @example create a float metric.
    let floatTest = tsm.float('frontend/float_test');
    floatTest.set(1.0);

    @example create a float counter metric.
    let floatCounterTest = tsm.counter('frontend/floatcounter_test');
    floatCounterTest.add(1);

    @example create an int metric.
    let intTest = tsm.int('frontend/int_test');
    intTest.set(1);

    @example create a string metric.
    let stringTest = tsm.string('frontend/string_test');
    stringTest.set('foo');
  */
  class TSMonClient {
    /**
     * @constructor
     */
    constructor(reportPath="/_/jstsmon", xsrfToken=null) {
      this._reportPath = reportPath;
      this._xsrfToken = xsrfToken;
      this._metrics = new Map();
      this._metricValues = new Map();
      this._flushIntervalMs = FLUSH_THRESHOLD_MS;
      this._flushTimer = setTimeout(() => {
        this._onFlush();
      }, this._flushIntervalMs);
      this._initTimeSeconds = Math.floor(new Date().getTime() / 1e3);
    }

    _onFlush() {
      this.flush();
      this._flushTimer = setTimeout(() => {
        this._onFlush();
      }, this._flushIntervalMs);
    }

    /** Returns the current time in milliseconds. */
    now() {
      return new Date().getTime();
    }

    /** Sends buffered metric measurements back to the server.
     * The JSON format should conform to the expectations documented in
     * handler here: https://cs.chromium.org/chromium/infra/appengine_module/gae_ts_mon/handlers.py?rcl=b3905d5ec3cb71fd91ed4fbf97e1e7671cb9090f&l=113
    */
    flush() {
      const values = this._metricValues;

      this._metricValues = new Map();
      // transform buf into a list of rawMetricValue objects:

      // Maps metric name to list of values grouped by field settings.
      const metricsByName = new Map();
      // Group measurements by metric name.
      for (const [key, value] of values) {
        let measurement = JSON.parse(key);
        // Re-build the fields map out of the canonicalized array key.
        if (measurement.fields) {
          const m = {};
          measurement.fields.forEach((e) => {
            m[e[0]] = e[1];
          })
          measurement.fields = m;
        }
        // Combine the key and values so the measurement object
        // has all the info we need to report.
        measurement = Object.assign(measurement, value);
        if (!metricsByName.has(measurement.name)) {
          metricsByName.set(measurement.name, []);
        }
        metricsByName.get(measurement.name).push(measurement);
      }
      // Now create one rawMetricValue per grouped set of measurements:
      const rawMetricValues = [];
      for (const [metricName, metricCells] of metricsByName) {
        const met = this._metrics.get(metricName);
        const cells = metricCells.map(cell => {
          // Strip out everything but the value and fields because the extra
          // data is promoted out to a rawMetricValue obj for the entire list of
          // cell data.
          let cellValue = cell.value;
          if (cellValue instanceof Distribution) {
            cellValue = {
              sum: cellValue.sum,
              count: cellValue.count,
              buckets: [...cellValue.buckets.entries()]
            };
          }
          return {
            value: cellValue,
            fields: cell.fields,
            start_time: this._initTimeSeconds,
          };
        });

        const fieldsObj = {};
        for (let [k, v] of met.info.Fields) {
          fieldsObj[k] = v;
        }
        const info = {
          Name: met.info.Name,
          Desription: met.info.Description,
          Fields: fieldsObj,
          ValueType: met.info.ValueType,
        };
        let rawMetricValue = {
          MetricInfo: info,
          MetricMetadata: met.metadata,
          Cells: cells,
        };

        rawMetricValues.push(rawMetricValue);
      }

      this.fetchImpl(rawMetricValues)
        .then(resp => {
          console.log("ts_mon response", resp);
          return resp.text();
        })
        .then(text => {
          if (text !== 'Ok.') {
            console.error('Non-ok response body:', text);
          }
        })
        .catch(error => {
          console.error("Failed to report ts_mon metrics.", error);
        });
    }

    /**
     * Override this method in a subclass to customize the structure of the
     * request sent to the back-end.
     *
     * @param {Array<Object>} an Array of raw metric values, defined in flush().
     * @returns {Promise} a Promise that resolves an HTTP Response.
     */
    fetchImpl(rawMetricValues) {
      return fetch(this._reportPath, {
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          metrics: rawMetricValues,
          token: this._xsrfToken,
        }),
      });
    }

    /**
     *
     * @param {String} name metric name
     * @param {Map<String, *>} fields map of field values
     */
    _metricKey(name, fields) {
      const fieldArray = [];
      if (fields) {
        for (const [key, value] of fields) {
          fieldArray.push([key, value]);
        }
        fieldArray.sort((a, b) => { return a[0] < b[0] ? -1 : 1});
      }
      return JSON.stringify({name: name, fields: fieldArray});
    }

    /**
     * Records one metric measurement, possibly buffering and/or flushing any
     * previously buffered measurements to the server.
     * @param {TSMetric} metric the metric to report.
     * @param {Object} value the value of the sample.
     * @param {Map<String, *>} fields map of fields to report with the sample.
     * @param {Boolean} cumulative whether the metric is cumulative.
     */
    _measure(metric, value, fields, cumulative) {
      const expectedFieldLen = metric.info.Fields
        ? metric.info.Fields.size
        : 0;
      const gotFieldLen = fields ? fields.size : 0;
      if (expectedFieldLen != gotFieldLen) {
        throw `field count ${
          metric.name
        }: ${expectedFieldLen} != ${gotFieldLen}`;
      }
      let key = this._metricKey(metric.name, fields);
      if (!this._metricValues.has(key)) {
        this._metricValues.set(key, {
          value: metric.defaultValue(),
        });
      }
      let current = this._metricValues.get(key);

      if (cumulative) {
        if (current.value instanceof Distribution) {
          current.value.add(value);
        } else {
          current += value;
        }
      } else {
        if (current.value instanceof Distribution) {
          current.value.set(value);
        } else {
          current.value = value;
        }
      }
      this._metricValues.set(key, current);
    }

    /**
     * @param {TSMetric} metric the metric to report.
     * @param {Object} value the value of the sample.
     * @param {Map<String, *>} fields map of fields to report with the sample.
     */
    add(metric, value, fields) {
      this._measure(metric, value, fields, true);
    }

    /**
     * @param {TSMetric} metric the metric to report.
     * @param {Object} value the value of the sample.
     * @param {Map<String, *>} fields map of fields to report with the sample.
     */
    set(metric, value, fields) {
      this._measure(metric, value, fields, false);
    }

    _register(name, met) {
      if (this._metrics.has(name)) {
        throw `${name} is already registered as a metric`;
      }
      this._metrics.set(name, met);
    }

    /** Returns a new boolean metric. */
    bool(name, desc, metadata, fields) {
      const ret = new TSSetter(
        this,
        ValueType.BOOL,
        name,
        desc,
        metadata,
        fields
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new counter metric. */
    counter(name, desc, metadata, fields) {
      const ret = new TSAdder(
        this,
        ValueType.CUMULATIVE_INT,
        name,
        desc,
        metadata,
        fields
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new cumulative distribution metric. */
    cumulativeDistribution(name, desc, metadata, fields, bucketer) {
      // Should return a Distribution.
      const ret = new TSCumulativeDistribution(
        this,
        ValueType.CUMULATIVE_DISTRIBUTION,
        name,
        desc,
        metadata,
        fields,
        bucketer
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new non-cumulative distribution metric. */
    nonCumulativeDistribution(name, desc, metadata, fields, bucketer) {
      const ret = new TSNonCumulativeDistribution(
        this,
        ValueType.NON_CUMULATIVE_DISTRIBUTION,
        name,
        desc,
        metadata,
        fields,
        bucketer
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new float metric. */
    float(name, desc, metadata, fields) {
      const ret = new TSSetter(
        this,
        ValueType.NON_CUMULATIVE_FLOAT,
        name,
        desc,
        metadata,
        fields
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new int metric. */
    int(name, desc, metadata, fields) {
      const ret = new TSSetter(
        this,
        ValueType.NON_CUMULATIVE_INT,
        name,
        desc,
        metadata,
        fields
      );
      this._register(name, ret);

      return ret;
    }

    /** Returns a new string metric. */
    string(name, desc, metadata, fields) {
      const ret = new TSSetter(
        this,
        ValueType.STRING,
        name,
        desc,
        metadata,
        fields
      );
      this._register(name, ret);

      return ret;
    }

    static stringField(name) {
      return { Name: name, Type: FieldType.STRING };
    }

    static intField(name) {
      return { Name: name, Type: FieldType.INT };
    }

    static boolField(name) {
      return { Name: name, Type: FieldType.BOOL };
    }

    static unitMetadata(metricDataUnit) {
      return { Units: metricDataUnit };
    }

    static fixedWidthBucketer(width, opt_numFiniteBuckets) {
      return new Bucketer(width, 0,
          opt_numFiniteBuckets == undefined ? 100 : opt_numFiniteBuckets);
    }

    static geometricBucketer(opt_growthFactor, opt_numFiniteBuckets, opt_scale) {
      return new Bucketer(0,
          opt_growthFactor == undefined ? Math.pow(10, 0.2) : opt_growthFactor,
          opt_numFiniteBuckets == undefined ? 100 : opt_numFiniteBuckets,
          opt_scale == undefined ? 1 : opt_scale);
    }
  }

  /**
   * A base class for different metric types.
   */
  class TSMetric {
    /**
     * @constructor
     * @param {TSMonClient} tsMon
     * @param {ValueType} vt
     * @param {String} name
     * @param {String} desc
     * @param {Object} metadata
     * @param {Map<String, *>} fields
     */
    constructor(tsMon, vt, name, desc, metadata, fields) {
      this.tsMon = tsMon;
      this.name = name;
      this.info = {
        Name: name,
        Description: desc,
        Fields: fields,
        ValueType: vt
      };
      this.metadata = metadata;
    }

    defaultValue() {
      return 0;
    }
  }

  class TSAdder extends TSMetric {
    /**
     * @param {*} v value
     * @param {Map<String, *>} fields map of field name to field value
     */
    add(v, fields) {
      this.tsMon.add(this, v, fields);
    }
  }

  class TSSetter extends TSMetric {
    /**
     * @param {*} v value
     * @param {Map<String, *>} fields map of field name to field value
     */
    set(v, fields) {
      this.tsMon.set(this, v, fields);
    }
  }

  class TSCumulativeDistribution extends TSAdder {
    constructor(tsMon, vt, name, desc, metadata, fields, bucketer) {
      super(tsMon, vt, name, desc, metadata, fields);
      this.bucketer = bucketer || TSMonClient.geometricBucketer();
    }

    defaultValue() {
      return new Distribution(this.bucketer);
    }
  }

  class TSNonCumulativeDistribution extends TSSetter {
    constructor(tsMon, vt, name, desc, metadata, fields, bucketer) {
      super(tsMon, vt, name, desc, metadata, fields);
      this.bucketer = bucketer || TSMonClient.geometricBucketer();
    }

    defaultValue() {
      return new Distribution(this.bucketer);
    }
  }



  /** Distribution is a value type for distribution metrics. */
  class Distribution {
    constructor(bucketer) {
      this.bucketer = bucketer;
      this.sum = 0;
      this.count = 0;
      this.buckets = new Map();
    }

    add(value) {
      const bucket = this.bucketer.bucketForValue(value);
      const curr = this.buckets.get(bucket) || 0;
      this.buckets.set(bucket, curr + 1);
      this.sum += value;
      this.count++;
    }
  }

  class Bucketer {
    constructor(width, growthFactor, numFiniteBuckets, opt_scale) {
      this.width = width;
      if (numFiniteBuckets < 0) {
        throw new Error(`Invalid numFiniteBuckets: ${numFiniteBuckets}`);
      }
      if (width != 0 && growthFactor != 0) {
        throw new Error(`Bucketer must be created with either a width or a growth factor, not both.`);
      }
      if (width < 0) {
        throw new Error(`Bucketer width must be > 0: ${width}`);
      }
      this.width = width;
      this.growthFactor = growthFactor;
      this.numFiniteBuckets = numFiniteBuckets;
      this.totalBuckets = numFiniteBuckets + 2;
      this.underflowBucket = 0;
      this.overflowBucket = this.totalBuckets - 1;
      this.scale = opt_scale || 1.0;

      if (this.width != 0) {
        this._lowerBounds = [-Infinity, ...this._linearBounds()];
      } else {
        this._lowerBounds = [-Infinity, ...this._exponentialBounds()];
      }

      if (this._lowerBounds.length != this.totalBuckets) {
        throw new Error(`lowerBounds.length != totalBuckets`);
      }

      this._lowerBounds.forEach((curr, i) => {
        if (i == this._lowerBounds.length - 2) {
          return;
        }
        const next = this._lowerBounds[i + 1];
        if (next <= curr) {
          throw new Error(`bucket boundaries must be monotonically increasing: ${curr}, ${next}`);
        }
      });
    }

    _linearBounds() {
      let ret = [];
      for (let i = 0; i < this.numFiniteBuckets + 1; i++) {
        ret[i] = this.width * i;
      }
      return ret;
    }

    _exponentialBounds() {
      let ret = [];
      for (let i = 0; i < this.numFiniteBuckets + 1; i++) {
        ret[i] = this.scale * Math.pow(this.growthFactor, i);
      }
      return ret;
    }

    _bisect(array, value) {
      // TODO: binary search.
      for (var i = 0; i < array.length; i++) {
        if (array[i] > value) return i;
      }
      return array.length;
    }

    bucketForValue(value) {
      return this._bisect(this._lowerBounds, value) - 1;
    }

    bucketBoundaries(bucket) {
      if (bucket < 0 || bucket >= this.totalBuckets) {
        throw new Error(`bucket ${bucket} out of range`);
      }
      if (bucket == this.totalBuckets - 1) {
        return [this._lowerBounds[bucket], Infinity];
      }
      return [this._lowerBounds[bucket], this._lowerBounds[bucket + 1]];
    }
  }

  return {
    Distribution,
    TSMonClient,
    ValueType,
    FieldType
  };
})();
