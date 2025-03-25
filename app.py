from flask import Flask, render_template, request, redirect, url_for, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import io, csv
import pandas as pd
from dateutil.relativedelta import relativedelta
from flask_apscheduler import APScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'  # Change this for production!

db = SQLAlchemy(app)

# --------------------------
# Database Models
# --------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)  # plain-text (not secure!)
    accounts = db.relationship('Account', backref='user', lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    initial_balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # The cascade line ensures that when an Account is deleted,
    # all associated Transactions get deleted, too.
    transactions = db.relationship(
        'Transaction',
        backref='account',
        lazy=True,
        cascade="all, delete-orphan"
    )

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(120))
    amount = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)  # computed: previous balance + amount
    category = db.Column(db.String(80), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

    # Recurring Transaction Fields
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_date = db.Column(db.Date, nullable=True)
    frequency = db.Column(db.String(20), nullable=True)

# --------------------------
# APScheduler Setup
# --------------------------
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())

scheduler = APScheduler()

def check_recurring_transactions():
    """Job to check for recurring transactions due and create new transactions, 
       updating the recurring date based on the fixed schedule."""
    with app.app_context():
        today = date.today()
        print(f"[APScheduler] Checking recurring transactions for {today}")
        
        # Find all recurring transactions that are due or overdue.
        recurring_txns = Transaction.query.filter(
            Transaction.is_recurring == True,
            Transaction.recurring_date <= today
        ).all()
        
        for txn in recurring_txns:
            # Get the most recent transaction balance for the account.
            last_txn = Transaction.query.filter_by(account_id=txn.account_id)\
                                        .order_by(Transaction.date.desc(), Transaction.id.desc()).first()
            if last_txn:
                new_balance = last_txn.balance + txn.amount
            else:
                account = Account.query.get(txn.account_id)
                new_balance = account.initial_balance + txn.amount

            # Calculate next recurrence based on the stored recurring_date rather than today.
            if txn.frequency == 'monthly':
                next_date = txn.recurring_date + relativedelta(months=+1)
            elif txn.frequency == 'yearly':
                next_date = txn.recurring_date + relativedelta(years=+1)
            else:
                next_date = None

            # Create a new recurring transaction.
            new_txn = Transaction(
                date=today,  # The new transaction date is today.
                description=txn.description + " (Recurring)",
                amount=txn.amount,
                balance=new_balance,
                category=txn.category,
                account_id=txn.account_id,
                is_recurring=True,
                recurring_date=next_date,
                frequency=txn.frequency
            )
            db.session.add(new_txn)
            # Update the original transaction's recurring_date so that it won't trigger again.
            txn.recurring_date = next_date
        db.session.commit()


# Add job to run every day
scheduler.add_job(
    id='RecurringTransactionJob',
    func=check_recurring_transactions,
    trigger='interval',
    days=1,
    replace_existing=True
)

scheduler.init_app(app)
scheduler.start()

# --------------------------
# Routes
# --------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

# Custom route to serve CSS files from templates/css
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('templates/css', filename)

# Custom route to serve JavaScript files from templates/scripts
@app.route('/scripts/<path:filename>')
def serve_scripts(filename):
    return send_from_directory('templates/scripts', filename)

# --- User Registration ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "User already exists. Please choose a different username."
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        # Optionally create default accounts for the user
        # bank_account = Account(name="Bank of America", type="bank", initial_balance=0.0, user_id=new_user.id)
        # credit_account = Account(name="Discover", type="credit", initial_balance=0.0, user_id=new_user.id)
        # db.session.add_all([bank_account, credit_account])
        # db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html')

# --- User Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials", 401
    return render_template('login.html')

# --- Logout ---
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# --- Dashboard: Shows key values, list of transactions, add new transaction, filter/export ---
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    # Try to get filter dates from query parameters.
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    month_str = request.args.get('month')  # New: month in "YYYY-MM" format
    filter_account_id = request.args.get('filter_account_id')
    start_date = end_date = None

    if month_str:
        # If a month filter is provided, calculate the first and last day of that month.
        try:
            start_date = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
            # End date is computed by adding one month and subtracting one day.
            end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
        except Exception as e:
            print("Month parsing error:", e)
    elif start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except Exception as e:
            print("Date parsing error:", e)
    
    # If still no filter dates, default to the current month.
    if not (start_date and end_date):
        today = date.today()
        start_date = today.replace(day=1)
        end_date = (today.replace(day=1) + relativedelta(months=+1)) - timedelta(days=1)
    
    # Get transactions filtered by date range.
    transactions = []
    if filter_account_id:
        query = Transaction.query.filter_by(account_id=filter_account_id)
        query = query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
        transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    else:
        for account in user.accounts:
            query = Transaction.query.filter_by(account_id=account.id)
            query = query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
            transactions += query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()

    # Calculate totals per category.
    category_totals = {}
    for txn in transactions:
        category_totals[txn.category] = category_totals.get(txn.category, 0) + txn.amount

    # Compute account balances.
    account_balances = {}
    for account in user.accounts:
        last_txn = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
        if last_txn:
            account_balances[account.name] = last_txn.balance
        else:
            account_balances[account.name] = account.initial_balance

    # Calculate overall total balance.
    total_balance = 0.0
    for account in user.accounts:
        if account.type.lower() == 'bank':
            total_balance += account_balances.get(account.name, 0)
        elif account.type.lower() == 'credit':
            total_balance -= account_balances.get(account.name, 0)
        else:
            total_balance += account_balances.get(account.name, 0)

    return render_template('dashboard.html',
                           user=user,
                           transactions=transactions,
                           category_totals=category_totals,
                           account_balances=account_balances,
                           total_balance=total_balance,
                           start_date=start_date.strftime('%Y-%m-%d'),
                           end_date=end_date.strftime('%Y-%m-%d'),
                           filter_account_id=filter_account_id,
                           selected_month=month_str if month_str else start_date.strftime('%Y-%m'))


# --- Add a New Transaction ---
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    account_id = request.form['account_id']
    date_str = request.form['date']
    description = request.form['description']
    amount = float(request.form['amount'])
    category = request.form['category']
    
    # Convert the date_str from the form to a date object.
    # HTML date input returns date in 'YYYY-MM-DD' format.
    txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    account = Account.query.get(account_id)
    effective_amount = -amount if account.type.lower() == "credit" else amount
    
    last_txn = Transaction.query.filter_by(account_id=account_id)\
                                  .order_by(Transaction.date.desc(), Transaction.id.desc()).first()
    new_balance = last_txn.balance + effective_amount if last_txn else account.initial_balance + effective_amount

    is_recurring_input = request.form.get("is_recurring", "no")
    is_recurring = True if is_recurring_input.lower() == "yes" else False
    # Use the transaction date as the recurring date if it's recurring.
    recurring_date = txn_date if is_recurring else None
    frequency = request.form.get("frequency", "").strip() if is_recurring else None

    new_txn = Transaction(
        date=txn_date,
        description=description,
        amount=amount,
        balance=new_balance,
        category=category,
        account_id=account_id,
        is_recurring=is_recurring,
        recurring_date=recurring_date,
        frequency=frequency
    )
    db.session.add(new_txn)
    db.session.commit()
    
    return redirect(url_for('dashboard', filter_account_id=account_id))


# --- Export Transactions as CSV ---
@app.route('/export')
def export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    start_date = end_date = None
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except Exception as e:
            print("Date parsing error:", e)
    
    transactions = []
    for account in user.accounts:
        query = Transaction.query.filter_by(account_id=account.id)
        if start_date and end_date:
            query = query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
        transactions += query.order_by(Transaction.date.asc(), Transaction.id.asc()).all()

    # Create CSV in memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Account", "Description", "Amount", "Balance", "Category"])
    for txn in transactions:
        cw.writerow([
            txn.date.strftime('%Y-%m-%d'),
            txn.account.name,
            txn.description,
            txn.amount,
            txn.balance,
            txn.category
        ])
    
    output = si.getvalue()
    
    # Generate filename based on the filter dates.
    if start_date and end_date:
        # Remove any leading zero from day by converting it to int before stringifying.
        start_str = start_date.strftime('%b') + "_" + str(start_date.day) + "_" + start_date.strftime('%y')
        end_str = end_date.strftime('%b') + "_" + str(end_date.day) + "_" + end_date.strftime('%y')
        filename = f"{start_str}_{end_str}_transactions.csv"
    else:
        filename = "transactions.csv"
    
    return send_file(
        io.BytesIO(output.encode('utf-8')),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )

    
# --- Removing Single Transaction --- #
@app.route('/remove_transaction/<int:transaction_id>', methods=['GET'])
def remove_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    txn = Transaction.query.get(transaction_id)
    if txn and txn.account.user_id == session['user_id']:
        account_id = txn.account.id  # Get the account id from the transaction
        db.session.delete(txn)
        db.session.commit()
        return redirect(url_for('dashboard', filter_account_id=account_id))
    return redirect(url_for('dashboard'))


# --- Removing Multiple transactions --- #
@app.route('/remove_transactions', methods=['POST'])
def remove_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    txn_ids = request.form.getlist('transaction_ids')
    # Try to preserve the current account filter from the query string.
    filter_account_id = request.args.get('filter_account_id')
    for txn_id in txn_ids:
        txn = Transaction.query.get(txn_id)
        if txn and txn.account.user_id == session['user_id']:
            db.session.delete(txn)
    db.session.commit()
    return redirect(url_for('dashboard', filter_account_id=filter_account_id))


# --- Adding New Bank Account --- #
@app.route('/add_account', methods=['POST'])
def add_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    name = request.form['name']
    account_type = request.form['type']  # Expected values: 'bank' for Debit or 'credit' for Credit
    
    # Create and add the new account with an initial balance of 0.0
    new_account = Account(name=name, type=account_type, initial_balance=0.0, user_id=user.id)
    db.session.add(new_account)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

# --- Remove Bank Account --- #
@app.route('/remove_account/<int:account_id>', methods=['GET'])
def remove_account(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    account = Account.query.get(account_id)
    # Remove the type check so any account belonging to the user can be removed.
    if account and account.user_id == session['user_id']:
        db.session.delete(account)
        db.session.commit()
    return redirect(url_for('dashboard'))

# --- Importing Transaction From File --- #
@app.route('/import_transactions', methods=['POST'])
def import_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    file = request.files.get('file')
    if not file:
        # Optionally flash an error message here
        return redirect(url_for('dashboard'))
    filename = file.filename.lower()
    try:
        # Process CSV or TSV files
        if filename.endswith('.csv') or filename.endswith('.tsv'):
            delimiter = ',' if filename.endswith('.csv') else '\t'
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream, delimiter=delimiter)
            for row in csv_input:
                # Expecting columns: Date, Account, Description, Amount, Category
                txn_date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
                description = row.get('Description', '')
                amount = float(row['Amount'])
                category = row.get('Category', '')
                account_name = row.get('Account', '')
                # Find account belonging to user with matching name
                account = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                if not account:
                    # Optionally, skip or create the account.
                    continue
                # Compute new balance based on last transaction or initial_balance.
                last_txn = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
                if last_txn:
                    new_balance = last_txn.balance + amount
                else:
                    new_balance = account.initial_balance + amount
                new_txn = Transaction(date=txn_date,
                                      description=description,
                                      amount=amount,
                                      balance=new_balance,
                                      category=category,
                                      account_id=account.id)
                db.session.add(new_txn)
            db.session.commit()
        # Process Excel files
        elif filename.endswith('.xls') or filename.endswith('.xlsx'):
            # Read all sheets from the Excel file into a dictionary of DataFrames.
            sheets_dict = pd.read_excel(file, sheet_name=None)
            
            # Define the expected columns.
            expected_cols = ['Date', 'Bank', 'Where/When', 'Money Earn/Spent', 'Balance', 'Category']
            sheet_dfs = []
            
            # Loop through each sheet in the workbook.
            for sheet_name, df_sheet in sheets_dict.items():
                # Clean column names: remove leading/trailing spaces.
                df_sheet.columns = df_sheet.columns.astype(str).str.strip()
                
                # Check if all expected columns exist in this sheet.
                if not set(expected_cols).issubset(df_sheet.columns):
                    print(f"Skipping sheet '{sheet_name}' because it doesn't contain all expected columns. Found columns: {df_sheet.columns.tolist()}")
                    continue
                
                # Keep only the expected columns.
                df_sheet = df_sheet[expected_cols]
                sheet_dfs.append(df_sheet)
            
            # If no valid sheet is found, exit the import.
            if not sheet_dfs:
                print("No valid sheets found with the expected columns.")
                return redirect(url_for('dashboard'))
            
            # Concatenate all valid sheets into one DataFrame.
            df = pd.concat(sheet_dfs, ignore_index=True)
            
            # Rename columns for internal consistency:
            # 'Bank' -> 'Account', 'Where/When' -> 'Description', 'Money Earn/Spent' -> 'Amount'
            df.rename(columns={
                'Bank': 'Account',
                'Where/When': 'Description',
                'Money Earn/Spent': 'Amount'
            }, inplace=True)
            
            # Convert the 'Date' column to date objects; invalid dates become NaT.
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
            
            # Drop rows with missing essential data to prevent processing errors.
            df.dropna(subset=['Date', 'Account', 'Description', 'Amount', 'Balance', 'Category'], inplace=True)
            
            # Process each account separately to update initial balances based on "Balance" rows.
            # We assume the first occurrence (in file order) is the initial balance.
            for account_name in df['Account'].unique():
                # Get all rows for this account in file order.
                df_account = df[df['Account'] == account_name]
                
                # Look for rows where Description equals "Balance".
                balance_rows = df_account[df_account['Description'] == "Balance"]
                if not balance_rows.empty:
                    # Use the first balance row to set the account's initial balance.
                    initial_balance = balance_rows.iloc[0]['Balance']
                    account_obj = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                    if account_obj:
                        account_obj.initial_balance = initial_balance
                    # Remove balance rows from further processing.
                    df = df.drop(balance_rows.index)
            
            # Do not re-sort so that the transactions remain in file order.
            
            # Process each transaction row in file order.
            for index, row in df.iterrows():
                txn_date = row['Date']
                description = row['Description']
                try:
                    amount = float(row['Amount'])
                except Exception as e:
                    continue  # Skip rows where the amount cannot be converted.
                category = row.get('Category', '')
                account_name = row['Account']
                
                # Find the matching account for the current user.
                account_obj = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                if not account_obj:
                    continue
                
                # Instead of recalculating the balance, use the imported Balance value.
                try:
                    imported_balance = float(row['Balance'])
                except Exception as e:
                    continue  # Skip rows where balance is not valid.
                
                new_txn = Transaction(
                    date=txn_date,
                    description=description,
                    amount=amount,
                    balance=imported_balance,
                    category=category,
                    account_id=account_obj.id
                )
                db.session.add(new_txn)
            
            db.session.commit()


            print("Import complete.")

        else:
            # Optionally flash an error message for unsupported file types.
            pass
    except Exception as e:
        print("Error processing file:", e)
        # Optionally flash an error message here.
    return redirect(url_for('dashboard'))
        
def next_recurring(rec_date, frequency):
    """Return the fixed next recurring date based on the stored recurring_date and frequency."""
    if rec_date is None:
        return None
    if frequency == 'monthly':
        return rec_date + relativedelta(months=+1)
    elif frequency == 'yearly':
        return rec_date + relativedelta(years=+1)
    else:
        return rec_date

def datetimeformat(value, format='%Y-%m-%d'):
    if value is None:
        return "N/A"
    return value.strftime(format)

app.jinja_env.filters['next_recurring'] = next_recurring
app.jinja_env.filters['datetimeformat'] = datetimeformat


# --------------------------
# Run the App
# --------------------------
if __name__ == '__main__':
    # Create tables if they don't exist (run once)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
