// -------------------------
// Account removal and Account Changing
// -------------------------
var accountSelect = document.getElementById("transactionAccountSelect");
var accountTypeDisplay = document.getElementById("accountTypeDisplay");
var modalOverlay = document.getElementById("modalOverlay");
var cancelAddAccount = document.getElementById("cancelAddAccount");
var removeAccountButton = document.getElementById("removeAccountButton");
var removeModalOverlay = document.getElementById("removeModalOverlay");
var cancelRemoveAccount = document.getElementById("cancelRemoveAccount");
var confirmRemoveAccount = document.getElementById("confirmRemoveAccount");
var selectedAccountId = null;

function updateAccountDisplay() {
  var selectedOption = accountSelect.options[accountSelect.selectedIndex];
  var transactionFormContainer = document.getElementById("transactionFormContainer");

  if (selectedOption.value === "add_account") {
    // Show the add account modal overlay.
    modalOverlay.style.display = "flex";
    accountTypeDisplay.innerText = "";
    removeAccountButton.style.display = "none";
    
    // If there's only one real account (i.e. one account plus the "Add New Account" option), hide the transaction form.
    if (accountSelect.options.length <= 2) {
      transactionFormContainer.style.display = "none";
    } else {
      transactionFormContainer.style.display = "block";
    }
  } else {
    // Hide modals and show the transaction form.
    modalOverlay.style.display = "none";
    transactionFormContainer.style.display = "block";
    
    // Get account type in lowercase and update the display.
    var accountType = (selectedOption.dataset.type || "").toLowerCase();
    var typeLabel = (accountType === "bank" || accountType === "credit")
                      ? accountType.charAt(0).toUpperCase() + accountType.slice(1)
                      : accountType;
    accountTypeDisplay.innerText = "Account Type: " + typeLabel;
    
    // Show the remove button if the account is either bank or credit.
    if (accountType === "bank" || accountType === "credit") {
      removeAccountButton.style.display = "inline-block";
    } else {
      removeAccountButton.style.display = "none";
    }
    
    // Only update the URL (and trigger a reload) if the filter_account_id parameter is not already set to this account.
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('filter_account_id') !== selectedOption.value) {
      urlParams.set('filter_account_id', selectedOption.value);
      // Replace the current search string, which triggers a page reload.
      window.location.search = urlParams.toString();
    }
  }
}

accountSelect.addEventListener("change", updateAccountDisplay);

document.addEventListener("DOMContentLoaded", function() {
  updateAccountDisplay();
  if (accountSelect.value === "add_account") {
    modalOverlay.style.display = "flex";
  }
});

cancelAddAccount.addEventListener("click", function(){
  modalOverlay.style.display = "none";
  accountSelect.selectedIndex = 0;
  updateAccountDisplay();
});

removeAccountButton.addEventListener("click", function(){
  var selectedOption = accountSelect.options[accountSelect.selectedIndex];
  selectedAccountId = selectedOption.value;
  var accountName = selectedOption.dataset.name;
  document.getElementById("removeAccountMessage").innerText =
    "Are you sure you want to remove the account '" + accountName + "'?";
  removeModalOverlay.style.display = "flex";
});

cancelRemoveAccount.addEventListener("click", function(){
  removeModalOverlay.style.display = "none";
});

confirmRemoveAccount.addEventListener("click", function(){
  if (selectedAccountId) {
    window.location.href = removeAccountUrlTemplate + selectedAccountId;
  }
});


// -------------------------
// Remove Selected Button for Transactions
// -------------------------
function updateRemoveSelectedButtonVisibility() {
  // Get all transaction checkboxes.
  var checkboxes = document.querySelectorAll("input[type='checkbox'][name='transaction_ids']");
  var removeSelectedButton = document.getElementById("removeSelectedButton");
  var anyChecked = false;
  
  checkboxes.forEach(function(checkbox) {
    if (checkbox.checked) {
      anyChecked = true;
    }
  });
  
  // Show button if any checkbox is checked; hide otherwise.
  removeSelectedButton.style.display = anyChecked ? "inline-block" : "none";
}

document.addEventListener("DOMContentLoaded", function() {
  // Attach change event to each transaction checkbox.
  var checkboxes = document.querySelectorAll("input[type='checkbox'][name='transaction_ids']");
  checkboxes.forEach(function(checkbox) {
    checkbox.addEventListener("change", updateRemoveSelectedButtonVisibility);
  });
  // Ensure correct visibility on page load.
  updateRemoveSelectedButtonVisibility();
});

// -------------------------
// Auto-submit filter form when both start and end dates are provided
// -------------------------
document.addEventListener("DOMContentLoaded", function() {
  var filterExportForm = document.getElementById('filterExportForm');
  var startDateInput = document.getElementById('start_date');
  var endDateInput = document.getElementById('end_date');

  function autoSubmitForm() {
    if (startDateInput.value && endDateInput.value) {
      // Auto-submit the form to filter transactions.
      filterExportForm.submit();
    }
  }

  startDateInput.addEventListener("change", autoSubmitForm);
  endDateInput.addEventListener("change", autoSubmitForm);
});