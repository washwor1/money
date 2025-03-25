document.addEventListener("DOMContentLoaded", function() {
    // Use the same approach as in data.js.
    let tokens = currentMonth.split("-");
    if (tokens[0].length === 4) {
        let temp = tokens[0];
        tokens[0] = tokens[1];
        tokens[1] = temp;
    }
    const formattedMonth = `${tokens[0].padStart(2, '0')}-${tokens[1]}`;
    const accountSelect = document.getElementById("accountSelect");
    let selectedAccount = accountSelect ? accountSelect.value : "";
  
    fetch(`/chart_data/${formattedMonth}?account_id=${selectedAccount}`)
      .then(response => response.json())
      .then(data => {
          let categoryTotals = {};
          data.datasets.forEach(ds => {
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
});
