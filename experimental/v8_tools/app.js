//  Vue component for drop-down menu; here the metrics,
//  stories and diagnostics are chosen through selection.
'use strict';
const app = new Vue({
  el: '#app',
  data: {
    sampleArr: [],
    guidValue: null,
    graph: new GraphData(),
    searchQuery: '',
    gridColumns: ['metric'],
    gridData: [],
    parsedMetrics: null,
    columnsForChosenDiagnostic: null,
    defaultGridData: [],
    typesOfPlot: ['Cumulative frequency plot', 'Dot plot'],
    chosenTypeOfPlot: null
  },

  methods: {
    //  Reset the table content by returning to the
    //  previous default way with all the components
    //  available.
    resetTableData() {
      this.gridData = this.defaultGridData;
      this.typesOfPlot = ['Cumulative frequency plot', 'Dot plot'];
    },

    //  Get all stories for a specific metric.
    getStoriesByMetric(entry) {
      const stories = [];
      for (const e of this.sampleArr) {
        if (e.name !== entry) {
          continue;
        }
        let nameOfStory = this.guidValue.get(e.diagnostics.stories);
        if (nameOfStory === undefined) {
          continue;
        }
        if (typeof nameOfStory !== 'number') {
          nameOfStory = nameOfStory[0];
        }
        stories.push(nameOfStory);
      }
      return _.uniq(stories);
    },

    //  Extract a diagnostic from a specific
    //  element (like metric). This should be 'parsed' because
    //  sometimes it might be either a number or a
    //  single element array.
    getDiagnostic(elem, diagnostic) {
      let currentDiagnostic = this.guidValue.
          get(elem.diagnostics[diagnostic]);
      if (currentDiagnostic === undefined) {
        return undefined;
      }
      if (currentDiagnostic !== 'number') {
        currentDiagnostic = currentDiagnostic[0];
      }
      return currentDiagnostic;
    },

    //  This method creates an object for multiple metrics,
    //  multiple stories and some diagnostics:
    //  {labelName: {storyName: { metricName: sampleValuesArray}}}
    computeDataForStackPlot(metricsDependingOnGrid,
        storiesName, labelsName) {
      const obj = {};
      for (const elem of metricsDependingOnGrid) {
        const currentDiagnostic = this.getDiagnostic(elem, 'labels');
        if (currentDiagnostic === undefined) {
          continue;
        }
        const nameOfStory = this.getDiagnostic(elem, 'stories');
        if (nameOfStory === undefined) {
          continue;
        }

        if (storiesName.includes(nameOfStory) &&
          labelsName.includes(currentDiagnostic)) {
          let storyToMetricValues = {};
          if (obj.hasOwnProperty(currentDiagnostic)) {
            storyToMetricValues = obj[currentDiagnostic];
          }

          let metricToSampleValues = {};
          if (storyToMetricValues.hasOwnProperty(nameOfStory)) {
            metricToSampleValues = storyToMetricValues[nameOfStory];
          }

          let array = [];
          if (metricToSampleValues.hasOwnProperty(elem.name)) {
            array = metricToSampleValues[elem.name];
          }
          array = array.concat(average(elem.sampleValues));
          metricToSampleValues[elem.name] = array;
          storyToMetricValues[nameOfStory] = metricToSampleValues;
          obj[currentDiagnostic] = storyToMetricValues;
        }
      }
      return obj;
    },

    //  Draw a bar chart.
    plotBarChart(data) {
      this.graph.xAxis('Story')
          .yAxis('Memory used (MiB)')
          .title('Labels')
          .setData(data, story => app.$emit('bar_clicked', story))
          .plotBar();
    },

    //  Draw a dot plot depending on the target value.
    //  This is mainly for results from the table.
    plotDotPlot(target, story, traces) {
      const openTrace = (label, index) => {
        window.open(traces[label][index]);
      };
      this.graph
          .yAxis('')
          .xAxis('Memory used (MiB)')
          .title(story)
          .setData(target, openTrace)
          .plotDot();
    },

    //  Draw a cumulative frequency plot depending on the target value.
    //  This is mainly for the results from the table.
    plotCumulativeFrequencyPlot(target, story, traces) {
      const openTrace = (label, index) => {
        window.open(traces[label][index]);
      };
      this.graph.yAxis('Cumulative frequency')
          .xAxis('Memory used (MiB)')
          .title(story)
          .setData(target, openTrace)
          .plotCumulativeFrequency();
    },

    plotStackBar(obj, title) {
      this.graph.xAxis('Stories')
          .yAxis('Memory used (MiB)')
          .title(title)
          .setData(obj)
          .plotStackedBar();
    },

    //  Being given a metric, a story, a diagnostic and a set of
    //  subdiagnostics (i.e. 3 labels from the total of 4), the
    //  method return the sample values for each subdiagnostic.
    getSubdiagnostics(
        getTargetValueFromSample, metric, story, diagnostic, diagnostics) {
      const result = this.sampleArr
          .filter(value => value.name === metric &&
          this.guidValue
              .get(value.diagnostics.stories)[0] ===
              story);

      const content = new Map();
      for (const val of result) {
        const diagnosticItem = this.guidValue.get(
            val.diagnostics[diagnostic]);
        if (diagnosticItem === undefined) {
          continue;
        }
        let currentDiagnostic = '';
        if (typeof diagnosticItem === 'number') {
          currentDiagnostic = diagnosticItem;
        } else {
          currentDiagnostic = diagnosticItem[0];
        }
        const targetValue = getTargetValueFromSample(val);
        if (content.has(currentDiagnostic)) {
          const aux = content.get(currentDiagnostic);
          content.set(currentDiagnostic, aux.concat(targetValue));
        } else {
          content.set(currentDiagnostic, targetValue);
        }
      }
      const obj = {};
      for (const [key, value] of content.entries()) {
        if (diagnostics === undefined ||
          diagnostics.includes(key.toString())) {
          obj[key] = value;
        }
      }
      return obj;
    },

    getSampleValues(sample) {
      const toMiB = (x) => (x / MiB).toFixed(5);
      const values = sample.sampleValues;
      return values.map(value => toMiB(value));
    },

    getTraceLinks(sample) {
      const traceId = sample.diagnostics.traceUrls;
      return this.guidValue.get(traceId);
    },
    //  Draw a plot by default with all the sub-diagnostics
    //  in the same plot;
    plotSingleMetricWithAllSubdiagnostics(metric, story, diagnostic) {
      const obj = this.getSubdiagnostics(
          this.getSampleValues, metric, story, diagnostic);
      const traces = this.targetForMultipleDiagnostics(
          this.getTraceLinks, metric, story, diagnostic);
      this.plotCumulativeFrequencyPlot(obj, story, traces);
    },

    //  Draw a plot depending on the target value which is made
    //  of a metric, a story, a diagnostic and a couple of sub-diagnostics
    //  and the chosen type of plot. All are chosen from the table.
    plotSingleMetric(metric, story, diagnostic,
        diagnostics, chosenPlot) {
      const target = this.targetForMultipleDiagnostics(
          this.getSampleValues, metric, story, diagnostic, diagnostics);
      const traces = this.targetForMultipleDiagnostics(
          this.getTraceLinks, metric, story, diagnostic, diagnostics);
      if (chosenPlot === 'Dot plot') {
        this.plotDotPlot(target, story, traces);
      } else {
        this.plotCumulativeFrequencyPlot(target, story, traces);
      }
    },

    //  Compute the target when the metric, story, diagnostics and
    //  sub-diagnostics are chosen from the table, not from the drop-down menu.
    //  It should be the same for both components but for now they should
    //  be divided.
    targetForMultipleDiagnostics(
        getTargetValueFromSample, metric, story, diagnostic, diagnostics) {
      if (metric === null || story === null ||
        diagnostic === null || diagnostics === null) {
        return undefined;
      }
      return this.getSubdiagnostics(
          getTargetValueFromSample, metric, story, diagnostic, diagnostics);
    }
  },

  computed: {
    gridDataLoaded() {
      return this.gridData.length > 0;
    },
    data_loaded() {
      return this.sampleArr.length > 0;
    }
  },

  watch: {
    //  Whenever a new metric/ story/ diagnostic is chosen
    //  this function will run for drawing a new type of plot.
    //  These items are chosen from the drop-down menu.
    filteredData() {
      this.plotCumulativeFrequency();
    },

    //  Whenever we have new inputs from the menu (parsed inputs that
    //  where obtained by choosing from the tree) these should be
    //  added in the table (adding the average sample value).
    //  Also it creates by default a stack plot for all the metrics
    //  obtained from the tree-menu, all the stories from the top-level
    //  metric and all labels.
    parsedMetrics() {
      const newGridData = [];
      for (const metric of this.parsedMetrics) {
        for (const elem of this.defaultGridData) {
          if (elem.metric === metric) {
            newGridData.push(elem);
          }
        }
      }
      this.gridData = newGridData;

      //  We select from sampleValues all the metrics thath
      //  corespond to the result from tree menu (gridData)
      const metricsDependingOnGrid = [];
      const gridMetricsName = [];

      for (const metric of this.gridData) {
        gridMetricsName.push(metric.metric);
      }

      for (const metric of this.sampleArr) {
        if (gridMetricsName.includes(metric.name)) {
          metricsDependingOnGrid.push(metric);
        }
      }
      //  The top level metric is taken as source in
      //  computing stories.
      const storiesName = this.getStoriesByMetric(this
          .gridData[0].metric);
      const labelsName = this.columnsForChosenDiagnostic;
      const obj = this.computeDataForStackPlot(metricsDependingOnGrid,
          storiesName, labelsName);
      this.plotStackBar(obj, newGridData[0].metric);
      //  From now on the user will be aible to switch between
      //  this 2 types of plot (taking into consideration that
      //  the scope of the tree-menu is to analyse using the
      //  the stacked plot and bar plot, we avoid for the moment
      //  other types of plot that should be actually used without
      //  using the tree menu)
      this.typesOfPlot = ['Bar chart plot', 'Stacked bar plot',
        'Cumulative frequency plot', 'Dot plot'];
      this.chosenTypeOfPlot = 'Stacked bar plot';
    }
  }
});
