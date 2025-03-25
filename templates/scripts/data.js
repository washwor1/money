document.addEventListener("DOMContentLoaded", function() {
  // Ensure currentMonth is in "MM-YYYY" format.
  let tokens = currentMonth.split("-");
  // If the first token is four characters long, assume it's "YYYY-MM" and swap.
  if (tokens[0].length === 4) {
      let temp = tokens[0];
      tokens[0] = tokens[1];
      tokens[1] = temp;
  }
  let month = Number(tokens[0]);
  let year = Number(tokens[1]);

  // Get the selected account from the dropdown.
  const accountSelect = document.getElementById("accountSelect");
  let selectedAccount = accountSelect ? accountSelect.value : "";

  // Fetch prediction data using AJAX.
  function fetchChartDataPrediction(y, m, accountId) {
    const monthStr = m.toString().padStart(2, '0');
    const monthYear = `${monthStr}-${y.toString()}`; // "MM-YYYY"
    // Append account_id as query parameter.
    const url = `/chart_data/prediction?month_year=${monthYear}&account_id=${accountId}`;
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert(data.error);
          return;
        }
        renderChart(data);
      })
      .catch(err => console.error("Error fetching prediction data:", err));
  }

  function renderChart(data) {
    const ctx = document.getElementById('myChart').getContext('2d');
    if (window.myChart && typeof window.myChart.destroy === 'function') {
      window.myChart.destroy();
    }
    const combinedDatasets = data.barDatasets.concat(data.lineDatasets);
    window.myChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.labels, // e.g., ["Jan 2025", "Feb 2025", ...]
        datasets: combinedDatasets
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'Last 4 Months Actual and Next Month Prediction'
          },
          tooltip: {
            mode: 'index',
            intersect: false
          },
          legend: {
            display: true
          }
        },
        scales: {
          x: { stacked: true },
          y: {
            stacked: true,
            beginAtZero: true,
            title: { display: true, text: 'Amount' }
          }
        }
      }
    });
  }

  // Function to update both chart and table.
  function updateData() {
    // Get current account value.
    let accountId = accountSelect ? accountSelect.value : "";
    fetchChartDataPrediction(year, month, accountId);
    fetchTableData(year, month, accountId);
  }

  // Fetch table data using AJAX.
  function fetchTableData(y, m, accountId) {
    const monthStr = m.toString().padStart(2, '0');
    const monthYear = `${monthStr}-${y.toString()}`; // "MM-YYYY"
    const url = `/chart_data/${monthYear}?account_id=${accountId}`;
    fetch(url)
      .then(response => response.json())
      .then(data => {
        let categoryTotals = {};
        data.datasets.forEach(ds => {
            // Remove trailing " Spent" or " Income"
            let cat = ds.label.replace(" Spent", "").replace(" Income", "");
            let val = ds.data[0] || 0;
            if (!categoryTotals[cat]) {
                categoryTotals[cat] = 0;
            }
            categoryTotals[cat] += val;
        });
        const tableBody = document.getElementById("tableBody");
        tableBody.innerHTML = "";
        for (let cat in categoryTotals) {
            let tr = document.createElement("tr");
            let tdCat = document.createElement("td");
            tdCat.textContent = cat;
            let tdVal = document.createElement("td");
            tdVal.textContent = categoryTotals[cat].toFixed(2);
            tr.appendChild(tdCat);
            tr.appendChild(tdVal);
            tableBody.appendChild(tr);
        }
      })
      .catch(err => console.error("Error fetching table data:", err));
  }

  // Initial data load.
  updateData();

  // When the account selection changes, update data without page refresh.
  if (accountSelect) {
    accountSelect.addEventListener("change", updateData);
  }

  // Navigation for months.
  function adjustMonth(delta) {
    let newMonth = month + delta;
    let newYear = year;
    if (newMonth < 1) {
      newMonth = 12;
      newYear -= 1;
    } else if (newMonth > 12) {
      newMonth = 1;
      newYear += 1;
    }
    const newMonthStr = newMonth.toString().padStart(2, '0');
    // Update URL without full page refresh.
    const newUrl = `/data/${newMonthStr}-${newYear}`;
    history.pushState(null, "", newUrl);
    // Update our global month and year values.
    month = newMonth;
    year = newYear;
    updateData();
    // Also update the display for the current month.
    updateDisplayMonthText();
  }

  document.getElementById("prevBtn").addEventListener("click", function() {
    adjustMonth(-1);
  });
  document.getElementById("nextBtn").addEventListener("click", function() {
    adjustMonth(1);
  });

  // Update display header using the global month and year variables.
  function updateDisplayMonthText() {
    const displayMonthEl = document.getElementById("displayMonth");
    if (displayMonthEl) {
      // Create a Date object (note: JavaScript Date months are 0-indexed)
      const dateObj = new Date(year, month - 1);
      // Format the date as "Mar 2025"
      const options = { month: 'short', year: 'numeric' };
      displayMonthEl.textContent = dateObj.toLocaleDateString(undefined, options);
    }
  }  
});

document.getElementById("monthFilterForm").addEventListener("submit", function(e) {
  e.preventDefault(); // Prevent the default form submission
  const monthValue = document.getElementById("monthInput").value; // Use the unique id "monthInput"
  if (monthValue) {
      // Convert "YYYY-MM" to "MM-YYYY"
      let [yr, mo] = monthValue.split("-");
      const ajaxMonthYear = `${mo}-${yr}`; // "MM-YYYY"
      window.location.href = `/data/${ajaxMonthYear}`;
  }
});

