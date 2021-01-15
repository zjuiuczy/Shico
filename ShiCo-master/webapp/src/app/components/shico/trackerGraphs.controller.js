(function() {
  'use strict';

  angular
    .module('shico')
    .controller('TrackerGraphsController', TrackerGraphsController);

  function TrackerGraphsController(GraphControlService) {
    var vm = this;

    // Share graph data from service to controller
    // so directive can find them.
    vm.streamGraph = GraphControlService.streamGraph;
    vm.forceGraph = GraphControlService.forceGraph;
    vm.scatterGraph = GraphControlService.scatterGraph;
    vm.vocabularies = GraphControlService.vocabularies;
    vm.slider_options = GraphControlService.slider_options;
    vm.getYearLabel = GraphControlService.getYearLabel;
    vm.yearsInSight = yearsInSight;
    vm.addBorder = addBorder;
    vm.downloadData = downloadData;
    // Changes
    vm.downloadPng = downloadPng;
    vm.downloadCsv = downloadCsv;
    function yearsInSight(yearIdx) {
      return (vm.forceGraph.currYearIdx - 1) <= yearIdx &&
              yearIdx <= (vm.forceGraph.currYearIdx + 1);
    }

    function addBorder(scope) {
      // Add border
      scope.svg.attr('style', 'border-style: solid');
    }

    function downloadData() {
      var rawData = GraphControlService.getRawData().stream;
      // allWords and allYears we already had -- we shouldn't need to build them again
      var allWords = new Set();
      var allYears = [];
      angular.forEach(rawData, function(wordValues, year) {
        allYears.push(year);
        angular.forEach(wordValues, function(weight, word) {
          allWords.add(word);
        });
      });
      // Create CSV file
      var headers = [ '' ].concat(allYears);
      var csvData = [ headers ];
      angular.forEach(allWords, function(word) {
        var row = [ word ];
        angular.forEach(allYears, function(year) {
          var val = (word in rawData[year]) ? rawData[year][word] : 0;
          row.push(val);
        });
        csvData.push(row);
      });
      return csvData;
    }

    function downloadPng(){
      // Download the Png
      var SVG1 = document.getElementsByTagName('svg')[0];
      var SVG2 = document.getElementsByTagName('svg')[1];
      var SVG3 = document.getElementsByTagName('svg')[2];
      SVG1.id = 0;
      SVG2.id = 1;
      SVG3.id = 2;
      saveSvgAsPng(document.getElementById("0"), "0.png");
      saveSvgAsPng(document.getElementById("1"), "1.png");
      saveSvgAsPng(document.getElementById("2"), "2.png");
    }

    function downloadCsv(){
      var rawData = GraphControlService.getRawData().vocabs;
      var allWords = new Set();
      var allYears = [];
      angular.forEach(rawData, function(wordValues, year) {
        allYears.push(year);
        angular.forEach(wordValues, function(weight, word) {
          allWords.add(word);
        });
      });
      // Create CSV file
      var headers = [ '' ].concat(allYears);
      var csvData = [ headers ];
      angular.forEach(allWords, function(word) {
        var row = [ word ];
        angular.forEach(allYears, function(year) {
          if (word in rawData[year]){
            var i = 0, helper = rawData[year][word].concat();
            angular.forEach(rawData[year][word], function(temp){
              // Get the first element
              helper[i++] = temp[0];
            });
          }
          var val = (word in rawData[year]) ? helper : 0;
          row.push(val);
        });
        csvData.push(row);
      });
      console.log(csvData);
      return csvData;
    }
  }
})();
