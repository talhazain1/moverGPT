// chart.js

// Fetch JSON metrics data from the API endpoint
async function fetchMetricsData() {
    try {
      const response = await fetch('/api/metrics/json');
      return await response.json();
    } catch (error) {
      console.error("Error fetching metrics JSON:", error);
      return null;
    }
  }
  
  // Aggregate request counts from 'flask_request_count'
  function aggregateRequestCounts(metricsData) {
    const samples = metricsData['flask_request_count'] || [];
    const counts = {};
    samples.forEach(sample => {
      const endpoint = sample.labels.endpoint;
      counts[endpoint] = (counts[endpoint] || 0) + parseFloat(sample.value);
    });
    const labels = Object.keys(counts);
    const values = labels.map(endpoint => counts[endpoint]);
    console.log("Aggregated request count data:", { labels, values });
    return { labels, values };
  }
  
  // Calculate average latency per endpoint using histogram metrics.
  // Expects: 'flask_request_latency_seconds_sum' and 'flask_request_latency_seconds_count'
  function calculateLatencyAverages(metricsData) {
    const sumSamples = metricsData['flask_request_latency_seconds_sum'] || [];
    const countSamples = metricsData['flask_request_latency_seconds_count'] || [];
    const latencyMap = {};
  
    sumSamples.forEach(sample => {
      const endpoint = sample.labels.endpoint;
      latencyMap[endpoint] = latencyMap[endpoint] || { sum: 0, count: 0 };
      latencyMap[endpoint].sum = parseFloat(sample.value);
    });
    countSamples.forEach(sample => {
      const endpoint = sample.labels.endpoint;
      latencyMap[endpoint] = latencyMap[endpoint] || { sum: 0, count: 0 };
      latencyMap[endpoint].count = parseFloat(sample.value);
    });
  
    const labels = Object.keys(latencyMap);
    if (labels.length === 0) {
      console.warn("No latency data found, using fallback values.");
      return { labels: ["No Metrics"], avgLatencies: [0] };
    }
    const avgLatencies = labels.map(endpoint => {
      const data = latencyMap[endpoint];
      return data.count > 0 ? data.sum / data.count : 0;
    });
    console.log("Aggregated latency data:", { labels, avgLatencies });
    return { labels, avgLatencies };
  }
  
  // Initialize and render charts using Chart.js
  async function initCharts() {
    const metricsData = await fetchMetricsData();
    if (!metricsData) {
      console.error("No metrics data available");
      return;
    }
  
    // Render the Request Count Bar Chart
    const requestCountData = aggregateRequestCounts(metricsData);
    const ctxCount = document.getElementById('requestCountChart').getContext('2d');
    new Chart(ctxCount, {
      type: 'bar',
      data: {
        labels: requestCountData.labels.length ? requestCountData.labels : ['No Data'],
        datasets: [{
          label: 'Request Count',
          data: requestCountData.values.length ? requestCountData.values : [0],
          backgroundColor: 'rgba(54, 162, 235, 0.6)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } }
      }
    });
  
    // Render the Request Latency Line Chart
    const latencyData = calculateLatencyAverages(metricsData);
    const ctxLatency = document.getElementById('requestLatencyChart').getContext('2d');
    new Chart(ctxLatency, {
      type: 'line',
      data: {
        labels: latencyData.labels,
        datasets: [{
          label: 'Avg Request Latency (s)',
          data: latencyData.avgLatencies,
          backgroundColor: 'rgba(255, 99, 132, 0.4)',
          borderColor: 'rgba(255, 99, 132, 1)',
          fill: false,
          tension: 0.1
        }]
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } }
      }
    });
  }
  
  window.onload = initCharts;
  