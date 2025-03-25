document.addEventListener("DOMContentLoaded", function() {
    // Logout handling.
    const logoutButton = document.getElementById("logoutButton");
    if (logoutButton) {
        logoutButton.addEventListener("click", function() {
            window.location.href = logoutUrl;
        });
    }
    
    // Account selection dropdown and related elements.
    const accountSelect = document.getElementById("accountSelect");
    const transactionFormContainer = document.getElementById("transactionFormContainer");
    const selectedAccountInput = document.getElementById("selectedAccountInput");

    // Function to update dashboard data via AJAX.
    function updateDashboard() {
        // If "add_account" is selected, do not update dashboard.
        if (accountSelect.value === "add_account") return;
        
        let accountId = accountSelect.value;
        let url = '/dashboard_data?';
        
        if (accountId) {
            url += `account_id=${accountId}&`;
        }
        
        // Check for start_date and end_date filters.
        const startDateEl = document.getElementById("start_date");
        const endDateEl = document.getElementById("end_date");
        if (startDateEl && endDateEl && startDateEl.value && endDateEl.value) {
            url += `start_date=${startDateEl.value}&end_date=${endDateEl.value}&`;
        }
        
        // Check for month filter.
        const monthEl = document.getElementById("month");
        if (monthEl && monthEl.value) {
            url += `month=${monthEl.value}&`;
        }
        
        // Remove trailing '&' if present.
        url = url.endsWith('&') ? url.slice(0, -1) : url;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Dashboard error:", data.error);
                    return;
                }
                // Update account balances.
                const balancesList = document.getElementById("balancesList");
                if (balancesList) {
                    let balancesHtml = "";
                    for (let acc in data.account_balances) {
                        balancesHtml += `<li>${acc}: $${Number(data.account_balances[acc]).toFixed(2)}</li>`;
                    }
                    balancesList.innerHTML = balancesHtml;
                }
                // Update total balance.
                const totalBalanceEl = document.getElementById("totalBalance");
                if (totalBalanceEl) {
                    totalBalanceEl.textContent = `Total Balance: $${Number(data.total_balance).toFixed(2)}`;
                }
                // Update transactions list.
                const transactionsList = document.getElementById("transactionsList");
                if (transactionsList) {
                    transactionsList.innerHTML = data.transactions_html;
                }
            })
            .catch(err => console.error("Error updating dashboard:", err));
    }
    
    
    // Initial dashboard update.
    updateDashboard();
    
    // Account selection change handler.
    if (accountSelect) {
        accountSelect.addEventListener("change", function() {
            let selectedValue = accountSelect.value;
            if (selectedValue === "") {
                // Hide add transaction form and clear hidden field.
                if (transactionFormContainer) {
                    transactionFormContainer.style.display = "none";
                }
                if (selectedAccountInput) {
                    selectedAccountInput.value = "";
                }
                // Hide remove account button.
                const removeAccountButton = document.getElementById("removeAccountButton");
                if (removeAccountButton) {
                    removeAccountButton.style.display = "none";
                }
                // Hide import button container.
                const importContainer = document.getElementById("importButtonContainer");
                if (importContainer) {
                    importContainer.style.display = "none";
                }
            } else if (selectedValue === "add_account") {
                // Show the add account modal.
                const modalOverlay = document.getElementById("modalOverlay");
                if (modalOverlay) {
                    modalOverlay.style.display = "flex";
                }
                // Attach event for cancel inside this branch if not already attached.
                const cancelAddAccount = document.getElementById("cancelAddAccount");
                if (cancelAddAccount) {
                    cancelAddAccount.addEventListener("click", function() {
                        const modalOverlay = document.getElementById("modalOverlay");
                        if (modalOverlay) {
                            modalOverlay.style.display = "none";
                        }
                        // Reset dropdown to default.
                        accountSelect.selectedIndex = 0;
                        updateDashboard();
                    });
                } else {
                    console.error("Cancel Add Account button not found.");
                }
            } else {
                // Valid account selected: show the add transaction form and set hidden field.
                if (selectedAccountInput) {
                    selectedAccountInput.value = selectedValue;
                }
                if (transactionFormContainer) {
                    transactionFormContainer.style.display = "block";
                }
                // Show the remove account button.
                const removeAccountButton = document.getElementById("removeAccountButton");
                if (removeAccountButton) {
                    removeAccountButton.style.display = "inline-block";
                }
                // Show the import button container.
                const importContainer = document.getElementById("importButtonContainer");
                if (importContainer) {
                    importContainer.style.display = "block";
                }
            }
            updateDashboard();
        });
    }
    
    // Remove Account Modal Handling.
    const removeAccountButton = document.getElementById("removeAccountButton");
    const cancelRemoveAccount = document.getElementById("cancelRemoveAccount");
    const confirmRemoveAccount = document.getElementById("confirmRemoveAccount");
    let selectedAccountId = null;
    if (removeAccountButton) {
        removeAccountButton.addEventListener("click", function() {
            const selectedOption = accountSelect.options[accountSelect.selectedIndex];
            selectedAccountId = selectedOption.value;
            const accountName = selectedOption.textContent;
            const removeMessage = document.getElementById("removeAccountMessage");
            if (removeMessage) {
                removeMessage.textContent = "Are you sure you want to remove the account '" + accountName + "'?";
            }
            const removeModalOverlay = document.getElementById("removeModalOverlay");
            if (removeModalOverlay) {
                removeModalOverlay.style.display = "flex";
            }
        });
    }
    if (cancelRemoveAccount) {
        cancelRemoveAccount.addEventListener("click", function() {
            const removeModalOverlay = document.getElementById("removeModalOverlay");
            if (removeModalOverlay) {
                removeModalOverlay.style.display = "none";
            }
        });
    }
    if (confirmRemoveAccount) {
        confirmRemoveAccount.addEventListener("click", function() {
            if (selectedAccountId) {
                window.location.href = `/remove_account/${selectedAccountId}`;
            }
        });
    }
    
    // Import Modal Handling.
    const importButton = document.getElementById("importButton");
    const importModalOverlay = document.getElementById("importModalOverlay");
    const cancelImport = document.getElementById("cancelImport");
    if (importButton) {
        importButton.addEventListener("click", function() {
            if (importModalOverlay) {
                importModalOverlay.style.display = "flex";
            }
        });
    }
    if (cancelImport) {
        cancelImport.addEventListener("click", function() {
            if (importModalOverlay) {
                importModalOverlay.style.display = "none";
            }
        });
    }
});
