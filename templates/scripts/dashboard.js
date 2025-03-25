// ----- New Account Selection Handling -----
var accountSelectionDropdown = document.getElementById("accountSelectionDropdown");
var transactionFormContainer = document.getElementById("transactionFormContainer");
var selectedAccountInput = document.getElementById("selectedAccountInput");
var removeAccountButton = document.getElementById("removeAccountButton");

accountSelectionDropdown.addEventListener("change", function() {
  var selectedValue = accountSelectionDropdown.value;
  if (selectedValue === "") {
    // No account selected; hide transaction form, remove button, and import button.
    transactionFormContainer.style.display = "none";
    selectedAccountInput.value = "";
    removeAccountButton.style.display = "none";
    var importContainer = document.getElementById("importButtonContainer");
    if (importContainer) {
      importContainer.style.display = "none";
    }
  } else if (selectedValue === "add_account") {
    // "Add New Account" selected: hide transaction form, remove and import buttons; show add account modal.
    transactionFormContainer.style.display = "none";
    removeAccountButton.style.display = "none";
    var importContainer = document.getElementById("importButtonContainer");
    if (importContainer) {
      importContainer.style.display = "none";
    }
    document.getElementById("modalOverlay").style.display = "flex";
  } else {
    // Valid account selected: update hidden field, show transaction form, remove account button, and import button.
    selectedAccountInput.value = selectedValue;
    transactionFormContainer.style.display = "block";
    removeAccountButton.style.display = "inline-block";
    var importContainer = document.getElementById("importButtonContainer");
    if (importContainer) {
      importContainer.style.display = "block";
    }
    
    // Update the URL query parameter if needed.
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('filter_account_id') !== selectedValue) {
      urlParams.set('filter_account_id', selectedValue);
      window.location.search = urlParams.toString();
    }
  }
});

// ----- Trigger change event on page load if an account is already selected ----- 
document.addEventListener("DOMContentLoaded", function() {
  // If the dropdown's value is non-empty and not "add_account", dispatch a change event.
  if (accountSelectionDropdown.value && accountSelectionDropdown.value !== "add_account") {
    accountSelectionDropdown.dispatchEvent(new Event('change'));
  }
});

// ----- Cancel button on the Add Account Popup -----
var cancelAddAccount = document.getElementById("cancelAddAccount");
cancelAddAccount.addEventListener("click", function() {
  document.getElementById("modalOverlay").style.display = "none";
  accountSelectionDropdown.selectedIndex = 0;
  transactionFormContainer.style.display = "none";
  removeAccountButton.style.display = "none";
  var importContainer = document.getElementById("importButtonContainer");
  if (importContainer) {
    importContainer.style.display = "none";
  }
});

// ----- Remove Account Button Handling -----
var selectedAccountId = null;
removeAccountButton.addEventListener("click", function() {
  var selectedOption = accountSelectionDropdown.options[accountSelectionDropdown.selectedIndex];
  selectedAccountId = selectedOption.value;
  var accountName = selectedOption.dataset.name;
  document.getElementById("removeAccountMessage").innerText =
    "Are you sure you want to remove the account '" + accountName + "'?";
  document.getElementById("removeModalOverlay").style.display = "flex";
});

var cancelRemoveAccount = document.getElementById("cancelRemoveAccount");
cancelRemoveAccount.addEventListener("click", function() {
  document.getElementById("removeModalOverlay").style.display = "none";
});

var confirmRemoveAccount = document.getElementById("confirmRemoveAccount");
confirmRemoveAccount.addEventListener("click", function() {
  if (selectedAccountId) {
    window.location.href = removeAccountUrlTemplate + selectedAccountId;
  }
});

// ----- Import Modal Handling -----
var importButton = document.getElementById("importButton");
var importModalOverlay = document.getElementById("importModalOverlay");
var cancelImport = document.getElementById("cancelImport");

importButton.addEventListener("click", function() {
  importModalOverlay.style.display = "flex";
});

cancelImport.addEventListener("click", function() {
  importModalOverlay.style.display = "none";
});

// ----- Remove Selected Button for Transactions -----
function updateRemoveSelectedButtonVisibility() {
  var checkboxes = document.querySelectorAll("input[type='checkbox'][name='transaction_ids']");
  var removeSelectedButton = document.getElementById("removeSelectedButton");
  var anyChecked = false;
  
  checkboxes.forEach(function(checkbox) {
    if (checkbox.checked) {
      anyChecked = true;
    }
  });
  
  removeSelectedButton.style.display = anyChecked ? "inline-block" : "none";
}

document.addEventListener("DOMContentLoaded", function() {
  var checkboxes = document.querySelectorAll("input[type='checkbox'][name='transaction_ids']");
  checkboxes.forEach(function(checkbox) {
    checkbox.addEventListener("change", updateRemoveSelectedButtonVisibility);
  });
  updateRemoveSelectedButtonVisibility();
});

// ----- Auto-submit Filter Form when both dates are provided -----
document.addEventListener("DOMContentLoaded", function() {
  var filterExportForm = document.getElementById('filterExportForm');
  var startDateInput = document.getElementById('start_date');
  var endDateInput = document.getElementById('end_date');

  function autoSubmitForm() {
    if (startDateInput.value && endDateInput.value) {
      filterExportForm.submit();
    }
  }

  startDateInput.addEventListener("change", autoSubmitForm);
  endDateInput.addEventListener("change", autoSubmitForm);
});

// ----- Recurring Transaction Handling -----
var categorySelect = document.getElementById("categorySelect");
var recurringSection = document.getElementById("recurringSection");
var isRecurringSelect = document.getElementById("isRecurringSelect");
var frequencySection = document.getElementById("frequencySection");
var frequencySelect = document.getElementById("frequencySelect");
var recurringDateSection = document.getElementById("recurringDateSection");

// When the category changes, show recurring options for Rent or Entertainment.
if (categorySelect) {
  categorySelect.addEventListener("change", function() {
    var selectedCategory = categorySelect.value;
    if (selectedCategory === "Rent" || selectedCategory === "Entertainment") {
      recurringSection.style.display = "block";
    } else {
      recurringSection.style.display = "none";
      // Reset the recurring options.
      if (isRecurringSelect) {
        isRecurringSelect.value = "no";
      }
      if (frequencySelect) {
        frequencySelect.value = "";
      }
      recurringDateSection.style.display = "none";
      frequencySection.style.display = "none";
    }
  });
}

// When the user selects if the transaction is recurring.
if (isRecurringSelect) {
  isRecurringSelect.addEventListener("change", function() {
    if (isRecurringSelect.value === "yes") {
      frequencySection.style.display = "block";
    } else {
      frequencySection.style.display = "none";
      if (frequencySelect) {
        frequencySelect.value = "";
      }
      recurringDateSection.style.display = "none";
    }
  });
}

// When the frequency is selected, show the recurring date field.
if (frequencySelect) {
  frequencySelect.addEventListener("change", function() {
    if (frequencySelect.value === "monthly" || frequencySelect.value === "yearly") {
      recurringDateSection.style.display = "block";
    } else {
      recurringDateSection.style.display = "none";
    }
  });
}
