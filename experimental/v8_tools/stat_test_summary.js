'use strict';
Vue.component('stat-test-summary', {
  props: {
    testResults: Array,
    referenceColumn: String,
  },
  template: '#stat-test-summary-template',
});
