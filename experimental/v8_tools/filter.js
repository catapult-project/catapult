'use strict';
const MiB = 1024 * 1024;
Vue.component('v-select', VueSelect.VueSelect);

const menu = new Vue({
  el: '#menu',
  data: {
    sampleArr: null,
    guidValueInfo: null,

    browser: null,
    subprocess: null,

    component: null,
    size: null,
    metricNames: null,

    browserOptions: [],
    subprocessOptions: [],

    subcomponent: null,
    subsubcomponent: null,

    componentMap: null,
    sizeMap: null,

    allLabels: [],
    testResults: [],
    referenceColumn: '',
    significanceTester: new MetricSignificance(),
  },

  computed: {
    //  Compute size options. The user will be provided with all
    //  sizes and the probe will be auto detected from it.
    sizeOptions() {
      if (this.sizeMap === null) {
        return undefined;
      }
      let sizes = [];
      for (const [key, value] of this.sizeMap.entries()) {
        sizes = sizes.concat(value);
      }
      return sizes;
    },

    //  The components are different depending on the type of probe.
    //  The probe is auto detected depending on the chosen size.
    //  Then the user is provided with the first level of components.
    componentsOptions() {
      if (this.componentMap === null || this.size === null) {
        return undefined;
      }
      for (const [key, value] of this.sizeMap.entries()) {
        if (value.includes(this.size)) {
          this.probe = key;
        }
      }
      const components = [];
      for (const [key, value] of this.componentMap.get(this.probe).entries()) {
        components.push(key);
      }
      return components;
    },

    //  Compute the options for the first subcomponent depending on the probes.
    //  When the user chooses a component, it might be a hierarchical one.
    firstSubcompOptions() {
      if (this.component === null) {
        return undefined;
      }
      const subcomponent = [];
      for (const [key, value] of this
          .componentMap.get(this.probe).get(this.component).entries()) {
        subcomponent.push(key);
      }
      return subcomponent;
    },

    //  In case when the component is from Chrome, the hierarchy might have more
    //  levels.
    secondSubcompOptions() {
      if (this.subcomponent === null) {
        return undefined;
      }
      const subcomponent = [];
      for (const [key, value] of this
          .componentMap
          .get(this.probe)
          .get(this.component)
          .get(this.subcomponent).entries()) {
        subcomponent.push(key);
      }
      return subcomponent;
    }
  },
  watch: {
    size() {
      this.component = null;
      this.subcomponent = null;
      this.subsubcomponent = null;
    },

    component() {
      this.subcomponent = null;
      this.subsubcomponent = null;
    },

    subcomponent() {
      this.subsubcomponent = null;
    },

    referenceColumn() {
      if (this.referenceColumn === null) {
        this.testResults = [];
        return;
      }
      this.significanceTester.referenceColumn = this.referenceColumn;
      this.testResults = this.significanceTester.mostSignificant();
    }

  },
  methods: {
    //  Build the available metrics upon the chosen items.
    //  The method applies an intersection for all of them and
    //  return the result as a collection of metrics that matched.
    apply() {
      const metrics = [];
      for (const name of this.metricNames) {
        if (this.browser !== null && name.includes(this.browser) &&
          this.subprocess !== null && name.includes(this.subprocess) &&
          this.component !== null && name.includes(this.component) &&
          this.size !== null && name.includes(this.size) &&
          this.probe !== null && name.includes(this.probe)) {
          if (this.subcomponent === null) {
            metrics.push(name);
          } else {
            if (name.includes(this.subcomponent)) {
              if (this.subsubcomponent === null) {
                metrics.push(name);
              } else {
                if (name.includes(this.subsubcomponent)) {
                  metrics.push(name);
                }
              }
            }
          }
        }
      }
      if (_.uniq(metrics).length === 0) {
        alert('No metrics found');
      } else {
        alert('You can pick a metric from drop-down');
        app.parsedMetrics = _.uniq(metrics);
      }
    }
  }
});

function average(arr) {
  return _.reduce(arr, function(memo, num) {
    return memo + num;
  }, 0) / arr.length;
}


//   Load the content of the file and further display the data.
function readSingleFile(e) {
  const file = e.target.files[0];
  if (!file) {
    return;
  }
  //  Extract data from file and distribute it in some relevant structures:
  //  results for all guid-related( for now they are not
  //  divided in 3 parts depending on the type ) and
  //  all results with sample-value-related and
  //  map guid to value within the same structure
  const reader = new FileReader();
  reader.onload = function(e) {
    const contents = extractData(e.target.result);
    const sampleArr = contents.sampleValueArray;
    const guidValueInfo = contents.guidValueInfo;
    const metricAverage = new Map();
    const allLabels = new Set();
    for (const e of sampleArr) {
      // This version of the tool focuses on analysing memory
      // metrics, which contain a slightly different structure
      // to the non-memory metrics.
      if (e.name.startsWith('memory')) {
        const { name, sampleValues, diagnostics } = e;
        const { labels, stories } = diagnostics;
        const label = guidValueInfo.get(labels)[0];
        allLabels.add(label);
        const story = guidValueInfo.get(stories)[0];
        menu.significanceTester.add(name, label, story, sampleValues);
      }
      if (metricAverage.has(e.name)) {
        const aux = metricAverage.get(e.name);
        aux.push(average(e.sampleValues));
        metricAverage.set(e.name, aux);
      } else {
        metricAverage.set(e.name, [average(e.sampleValues)]);
      }
    }
    menu.allLabels = Array.from(allLabels);
    //  The content for the default table: with name
    //  of the metric, the average value of the sample values
    //  plus an id. The latest is used to expand the row.
    //  It may disappear later.
    const tableElems = [];
    let id = 1;
    for (const [key, value] of metricAverage.entries()) {
      tableElems.push({
        id: id++,
        metric: key,
        averageSampleValues: average(value)
      });
    }
    app.gridData = tableElems;
    app.sampleArr = sampleArr;
    app.guidValue = guidValueInfo;

    let metricNames = [];
    sampleArr.map(e => metricNames.push(e.name));
    metricNames = _.uniq(metricNames);

    const result = parseAllMetrics(metricNames);
    menu.sampelArr = sampleArr;
    menu.guidValueInfo = guidValueInfo;

    menu.browserOptions = result.browsers;
    menu.subprocessOptions = result.subprocesses;
    menu.componentMap = result.components;
    menu.sizeMap = result.sizes;
    menu.metricNames = result.names;
  };
  reader.readAsText(file);
}

function extractData(contents) {
  /*
   *  Populate guidValue with guidValue objects containing
   *  guid and value from the same type of data.
   */
  const guidValueInfoMap = new Map();
  const result = [];
  const sampleValue = [];
  const dateRangeMap = new Map();
  const other = [];
  /*
   *  Extract every piece of data between <histogram-json> tags;
   *  all data is written between these tags
   */
  const reg = /<histogram-json>(.*?)<\/histogram-json>/g;
  let m = reg.exec(contents);
  while (m !== null) {
    result.push(m[1]);
    m = reg.exec(contents);
  }
  for (const element of result) {
    const e = JSON.parse(element);
    if (e.hasOwnProperty('sampleValues')) {
      const elem = {
        name: e.name,
        sampleValues: e.sampleValues,
        unit: e.unit,
        guid: e.guid,
        diagnostics: {}
      };
      if (e.diagnostics.hasOwnProperty('traceUrls')) {
        elem.diagnostics.traceUrls = e.diagnostics.traceUrls;
      }
      if (e.diagnostics.hasOwnProperty('benchmarkStart')) {
        elem.diagnostics.benchmarkStart = e.diagnostics.benchmarkStart;
      }
      if (e.diagnostics.hasOwnProperty('labels')) {
        elem.diagnostics.labels = e.diagnostics.labels;
      }
      if (e.diagnostics.hasOwnProperty('stories')) {
        elem.diagnostics.stories = e.diagnostics.stories;
      }
      if (e.diagnostics.hasOwnProperty('storysetRepeats')) {
        elem.diagnostics.storysetRepeats = e.diagnostics.storysetRepeats;
      }
      sampleValue.push(elem);
    } else {
      if (e.type === 'GenericSet') {
        guidValueInfoMap.set(e.guid, e.values);
      } else if (e.type === 'DateRange') {
        guidValueInfoMap.set(e.guid, e.min);
      } else {
        other.push(e);
      }
    }
  }

  return {
    guidValueInfo: guidValueInfoMap,
    guidMinInfo: dateRangeMap,
    otherTypes: other,
    sampleValueArray: sampleValue
  };
}
document.getElementById('file-input')
    .addEventListener('change', readSingleFile, false);
