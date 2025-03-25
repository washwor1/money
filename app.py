from flask import Flask, render_template, request, redirect, url_for, session, send_file, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, date, timedelta
import io, csv, hashlib, math
import pandas as pd
from dateutil.relativedelta import relativedelta
from flask_apscheduler import APScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'  # Change this for production!

db = SQLAlchemy(app)

app.jinja_env.globals.update(date=date)

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
    balance = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
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
    with app.app_context():
        today = date.today()
        print(f"[APScheduler] Checking recurring transactions for {today}")
        recurring_txns = Transaction.query.filter(
            Transaction.is_recurring == True,
            Transaction.recurring_date <= today
        ).all()
        for txn in recurring_txns:
            last_txn = Transaction.query.filter_by(account_id=txn.account_id)\
                                        .order_by(Transaction.date.desc(), Transaction.id.desc()).first()
            if last_txn:
                new_balance = last_txn.balance + txn.amount
            else:
                account = Account.query.get(txn.account_id)
                new_balance = account.initial_balance + txn.amount
            if txn.frequency == 'monthly':
                next_date = txn.recurring_date + relativedelta(months=+1)
            elif txn.frequency == 'yearly':
                next_date = txn.recurring_date + relativedelta(years=+1)
            else:
                next_date = None
            new_txn = Transaction(
                date=today,
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
            txn.recurring_date = next_date
        db.session.commit()

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

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('templates/css', filename)

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

# --- Dashboard ---
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    
    # --- Determine Date Filter ---
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    month_str = request.args.get('month')  # Expected in "YYYY-MM" format

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except Exception as e:
            print("Date parsing error:", e)
            start_date = date.today().replace(day=1)
            end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
    elif month_str:
        try:
            # Use the provided month (YYYY-MM) to calculate the start and end of that month.
            start_date = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
            end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
        except Exception as e:
            print("Month parsing error:", e)
            start_date = date.today().replace(day=1)
            end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
    else:
        # Default to the current month.
        start_date = date.today().replace(day=1)
        end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)

    # --- Get Account Filter ---
    filter_account_id = request.args.get('filter_account_id', "").strip()
    
    # If a specific account is selected, query its transactions; otherwise, leave the list empty.
    transactions = []
    if filter_account_id:
        try:
            account_id_int = int(filter_account_id)
            transactions = (Transaction.query.filter_by(account_id=account_id_int)
                            .filter(Transaction.date >= start_date, Transaction.date <= end_date)
                            .order_by(Transaction.date.desc(), Transaction.id.desc())
                            .all())
        except ValueError:
            transactions = []
    else:
        transactions = []  # When no specific account is selected, keep transactions empty.

    # --- Compute Totals & Balances ---
    category_totals = {}
    for txn in transactions:
        category_totals[txn.category] = category_totals.get(txn.category, 0) + txn.amount

    account_balances = {}
    for account in user.accounts:
        last_txn = (Transaction.query.filter_by(account_id=account.id)
                                     .order_by(Transaction.date.desc(), Transaction.id.desc())
                                     .first())
        if last_txn:
            account_balances[account.name] = last_txn.balance
        else:
            account_balances[account.name] = account.initial_balance

    total_balance = 0.0
    for account in user.accounts:
        if account.type.lower() == 'bank':
            total_balance += account_balances.get(account.name, 0)
        elif account.type.lower() == 'credit':
            total_balance -= account_balances.get(account.name, 0)
        else:
            total_balance += account_balances.get(account.name, 0)

    # --- Render Template ---
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




# Dashboard data for less refreshes
@app.route('/dashboard_data')
def dashboard_data():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    user = db.session.get(User, session['user_id'])
    account_id = request.args.get('account_id')
    
    # Check for date filters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    month_str = request.args.get('month')
    
    transactions_query = None
    if account_id:
        transactions_query = Transaction.query.filter_by(account_id=int(account_id))
    else:
        # Combine transactions from all accounts if no specific account is given.
        transactions_query = db.session.query(Transaction).filter(
            Transaction.account_id.in_([account.id for account in user.accounts])
        )
    
    # Apply date filter if provided
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            transactions_query = transactions_query.filter(
                Transaction.date >= start_date,
                Transaction.date <= end_date
            )
        except Exception as e:
            print("Date parsing error in dashboard_data:", e)
    elif month_str:
        try:
            start_date = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
            end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
            transactions_query = transactions_query.filter(
                Transaction.date >= start_date,
                Transaction.date <= end_date
            )
        except Exception as e:
            print("Month parsing error in dashboard_data:", e)
    
    transactions = transactions_query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    
    # Build HTML for the transaction list...
    transactions_html = ""
    for txn in transactions:
        remove_url = url_for('remove_transaction', transaction_id=txn.id)
        transactions_html += (
            "<tr>"
            f"<td><input type='checkbox' name='transaction_ids' value='{txn.id}'></td>"
            f"<td>{txn.date.strftime('%m/%d/%Y')}</td>"
            f"<td>{txn.account.name}</td>"
            f"<td>{txn.description}</td>"
            f"<td>{txn.amount:.2f}</td>"
            f"<td>{txn.balance:.2f}</td>"
            f"<td>{txn.category}</td>"
            f"<td>{'Yes' if txn.is_recurring else 'No'}</td>"
            f"<td>{txn.recurring_date if txn.recurring_date else '-'}</td>"
            f"<td><a href='{remove_url}' class='remove-link'>Remove</a></td>"
            "</tr>"
        )
    
    # Compute balances (same as before)
    account_balances = {}
    for account in user.accounts:
        last_txn = Transaction.query.filter_by(account_id=account.id)\
                     .order_by(Transaction.date.desc(), Transaction.id.desc()).first()
        if last_txn:
            account_balances[account.name] = last_txn.balance
        else:
            account_balances[account.name] = account.initial_balance
    
    total_balance = 0.0
    for account in user.accounts:
        if account.type.lower() == 'bank':
            total_balance += account_balances.get(account.name, 0)
        elif account.type.lower() == 'credit':
            total_balance -= account_balances.get(account.name, 0)
        else:
            total_balance += account_balances.get(account.name, 0)
    
    return jsonify({
        "account_balances": account_balances,
        "total_balance": total_balance,
        "transactions_html": transactions_html
    })




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
    txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    account = Account.query.get(account_id)
    effective_amount = -amount if account.type.lower() == "credit" else amount
    last_txn = Transaction.query.filter_by(account_id=account_id)\
                                  .order_by(Transaction.date.desc(), Transaction.id.desc()).first()
    new_balance = last_txn.balance + effective_amount if last_txn else account.initial_balance + effective_amount
    is_recurring_input = request.form.get("is_recurring", "no")
    is_recurring = True if is_recurring_input.lower() == "yes" else False
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
            start_date = datetime.strptime(start_date_str, '%m-%d-%Y').date()
            end_date = datetime.strptime(end_date_str, '%m-%d-%Y').date()
        except Exception as e:
            print("Date parsing error:", e)
    transactions = []
    for account in user.accounts:
        query = Transaction.query.filter_by(account_id=account.id)
        if start_date and end_date:
            query = query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
        transactions += query.order_by(Transaction.date.asc(), Transaction.id.asc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Account", "Description", "Amount", "Balance", "Category"])
    for txn in transactions:
        cw.writerow([
            txn.date.strftime('%m-%d-%Y'),
            txn.account.name,
            txn.description,
            txn.amount,
            txn.balance,
            txn.category
        ])
    output = si.getvalue()
    if start_date and end_date:
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

# --- Removing Single Transaction ---
@app.route('/remove_transaction/<int:transaction_id>', methods=['GET'])
def remove_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    txn = Transaction.query.get(transaction_id)
    if txn and txn.account.user_id == session['user_id']:
        account_id = txn.account.id
        db.session.delete(txn)
        db.session.commit()
        return redirect(url_for('dashboard', filter_account_id=account_id))
    return redirect(url_for('dashboard'))

# --- Removing Multiple Transactions ---
@app.route('/remove_transactions', methods=['POST'])
def remove_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    txn_ids = request.form.getlist('transaction_ids')
    filter_account_id = request.args.get('filter_account_id')
    for txn_id in txn_ids:
        txn = Transaction.query.get(txn_id)
        if txn and txn.account.user_id == session['user_id']:
            db.session.delete(txn)
    db.session.commit()
    return redirect(url_for('dashboard', filter_account_id=filter_account_id))

# --- Adding New Bank Account ---
@app.route('/add_account', methods=['POST'])
def add_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    name = request.form['name']
    account_type = request.form['type']
    new_account = Account(name=name, type=account_type, initial_balance=0.0, user_id=user.id)
    db.session.add(new_account)
    db.session.commit()
    return redirect(url_for('dashboard'))

# --- Remove Bank Account ---
@app.route('/remove_account/<int:account_id>', methods=['GET'])
def remove_account(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    account = Account.query.get(account_id)
    if account and account.user_id == session['user_id']:
        db.session.delete(account)
        db.session.commit()
    return redirect(url_for('dashboard'))

# --- Importing Transactions From File ---
@app.route('/import_transactions', methods=['POST'])
def import_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    file = request.files.get('file')
    if not file:
        return redirect(url_for('dashboard'))
    filename = file.filename.lower()
    try:
        if filename.endswith('.csv') or filename.endswith('.tsv'):
            delimiter = ',' if filename.endswith('.csv') else '\t'
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream, delimiter=delimiter)
            for row in csv_input:
                # Parse the date using MM-DD-YYYY format.
                txn_date = datetime.strptime(row['Date'], '%m-%d-%Y').date()
                description = row.get('Description', '')
                amount = float(row['Amount'])
                category = row.get('Category', '')
                account_name = row.get('Account', '')
                account = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                if not account:
                    continue
                last_txn = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
                if last_txn:
                    new_balance = last_txn.balance + amount
                else:
                    new_balance = account.initial_balance + amount
                new_txn = Transaction(
                    date=txn_date,
                    description=description,
                    amount=amount,
                    balance=new_balance,
                    category=category,
                    account_id=account.id
                )
                db.session.add(new_txn)
            db.session.commit()
        elif filename.endswith('.xls') or filename.endswith('.xlsx'):
            sheets_dict = pd.read_excel(file, sheet_name=None)
            expected_cols = ['Date', 'Bank', 'Where/When', 'Money Earn/Spent', 'Balance', 'Category']
            sheet_dfs = []
            for sheet_name, df_sheet in sheets_dict.items():
                df_sheet.columns = df_sheet.columns.astype(str).str.strip()
                if not set(expected_cols).issubset(df_sheet.columns):
                    print(f"Skipping sheet '{sheet_name}' because it doesn't contain all expected columns. Found columns: {df_sheet.columns.tolist()}")
                    continue
                df_sheet = df_sheet[expected_cols]
                sheet_dfs.append(df_sheet)
            if not sheet_dfs:
                print("No valid sheets found with the expected columns.")
                return redirect(url_for('dashboard'))
            df = pd.concat(sheet_dfs, ignore_index=True)
            df.rename(columns={
                'Bank': 'Account',
                'Where/When': 'Description',
                'Money Earn/Spent': 'Amount'
            }, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'], format='%m-%d-%Y', errors='coerce').dt.date
            df.dropna(subset=['Date', 'Account', 'Description', 'Amount', 'Balance', 'Category'], inplace=True)
            for account_name in df['Account'].unique():
                df_account = df[df['Account'] == account_name]
                balance_rows = df_account[df_account['Description'] == "Balance"]
                if not balance_rows.empty:
                    initial_balance = balance_rows.iloc[0]['Balance']
                    account_obj = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                    if account_obj:
                        account_obj.initial_balance = initial_balance
                    df = df.drop(balance_rows.index)
            for index, row in df.iterrows():
                txn_date = row['Date']
                description = row['Description']
                try:
                    amount = float(row['Amount'])
                except Exception as e:
                    continue
                category = row.get('Category', '')
                account_name = row['Account']
                account_obj = Account.query.filter_by(user_id=session['user_id'], name=account_name).first()
                if not account_obj:
                    continue
                try:
                    imported_balance = float(row['Balance'])
                except Exception as e:
                    continue
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
            pass
    except Exception as e:
        print("Error processing file:", e)
    return redirect(url_for('dashboard'))

def next_recurring(rec_date, frequency):
    if rec_date is None:
        return None
    if frequency == 'monthly':
        return rec_date + relativedelta(months=+1)
    elif frequency == 'yearly':
        return rec_date + relativedelta(years=+1)
    else:
        return rec_date

def datetimeformat(value, format='%m-%d-%Y'):
    if value is None:
        return "N/A"
    return value.strftime(format)

app.jinja_env.filters['next_recurring'] = next_recurring
app.jinja_env.filters['datetimeformat'] = datetimeformat

# Stable color for chart_data
def stable_color(category):
    h = int(hashlib.md5(category.encode('utf-8')).hexdigest(), 16)
    r = (h & 0xFF0000) >> 16
    g = (h & 0x00FF00) >> 8
    b = (h & 0x0000FF)
    return f"rgba({r}, {g}, {b}, 0.5)"

# --- Chart Data Endpoint for Current Month ---
@app.route('/chart_data/<month_year>')
def chart_data(month_year):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    # Get account_id from query parameters; if not provided, use first account.
    account_id = request.args.get('account_id')
    if account_id:
        account_ids = [int(account_id)]
    else:
        if user.accounts:
            account_ids = [user.accounts[0].id]
        else:
            return jsonify({"error": "No account found."}), 400

    try:
        parts = month_year.split("-")
        if len(parts) != 2:
            raise ValueError
        # Expecting format "MM-YYYY"
        month = int(parts[0])
        year = int(parts[1])
        start_date = date(year, month, 1)
        end_date = (start_date + relativedelta(months=+1)) - timedelta(days=1)
    except Exception as e:
        return jsonify({"error": "Invalid month-year format. Use MM-YYYY."}), 400

    results = db.session.query(
        func.strftime('%m-%Y', Transaction.date).label('month'),
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date,
        Transaction.account_id.in_(account_ids)
    ).group_by(Transaction.category).all()

    spent_map = {}
    income_map = {}
    categories_set = set()
    for m, category, total in results:
        categories_set.add(category)
        if total < 0:
            spent_map[category] = spent_map.get(category, 0) + abs(total)
        else:
            income_map[category] = income_map.get(category, 0) + total

    categories = sorted(list(categories_set))
    datasets = []
    for cat in categories:
        spent_val = spent_map.get(cat, 0)
        income_val = income_map.get(cat, 0)
        if spent_val > 0:
            datasets.append({
                "label": f"{cat} Spent",
                "data": [spent_val],
                "backgroundColor": stable_color(cat),
                "stack": "SpentStack"
            })
        if income_val > 0:
            datasets.append({
                "label": f"{cat} Income",
                "data": [income_val],
                "backgroundColor": stable_color(cat),
                "stack": "IncomeStack"
            })

    label_str = start_date.strftime('%b %Y')
    return jsonify({"labels": [label_str], "datasets": datasets})


# --- Chart Data Prediction Endpoint ---
@app.route('/chart_data/prediction')
def chart_data_prediction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    
    # Get target month_year and account_id from query parameters.
    month_year = request.args.get('month_year')
    if not month_year:
        month_year = date.today().strftime('%m-%Y')  # e.g. "04-2025"
    account_id = request.args.get('account_id')
    if account_id:
        account_ids = [int(account_id)]
    else:
        if user.accounts:
            account_ids = [user.accounts[0].id]
        else:
            return jsonify({"error": "No account found."}), 400

    try:
        parts = month_year.split("-")
        if len(parts) != 2:
            raise ValueError
        # Expecting format "MM-YYYY"
        month = int(parts[0])
        year = int(parts[1])
    except Exception as e:
        return jsonify({"error": "Invalid month-year format. Use MM-YYYY."}), 400

    # Define last 4 months: target month minus 3 up to target month.
    months = []
    for i in range(3, -1, -1):
        m_date = date(year, month, 1) - relativedelta(months=i)
        months.append(m_date)
    labels = [d.strftime('%b %Y') for d in months]

    # Build mapping: data_map[(month_str, category)] = total
    data_map = {}
    for m in months:
        start_date = m
        end_date = (m + relativedelta(months=+1)) - timedelta(days=1)
        results = db.session.query(
            func.strftime('%m-%Y', Transaction.date).label('m_str'),
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.date >= start_date,
            Transaction.date <= end_date,
            Transaction.account_id.in_(account_ids)
        ).group_by(func.strftime('%m-%Y', Transaction.date), Transaction.category).all()
        for m_str, category, total in results:
            data_map[(m_str, category)] = total

    all_categories = set(cat for (_, cat) in data_map.keys())

    category_data = {}
    for cat in all_categories:
        values = []
        for m in months:
            key = m.strftime('%m-%Y')
            val = data_map.get((key, cat), 0)
            values.append(val)
        category_data[cat] = values

    # Check if next month already has data.
    targetDate = date(year, month, 1)
    next_month_date = targetDate + relativedelta(months=+1)
    next_start = next_month_date
    next_end = (next_start + relativedelta(months=+1)) - timedelta(days=1)
    next_results = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.date >= next_start,
        Transaction.date <= next_end,
        Transaction.account_id.in_(account_ids)
    ).group_by(Transaction.category).all()

    barDatasets = []
    for cat, values in category_data.items():
        color = stable_color(cat)
        # Bar dataset for actual values for the 4 months; append 0 for next month initially.
        barDatasets.append({
            "label": f"{cat} Actual",
            "data": values + [0],
            "backgroundColor": color,
            "stack": "ActualStack"
        })

    lineDatasets = []
    if next_results:
        # If actual data exists for next month, update the bar datasets with that value.
        next_data = { category: total for category, total in next_results }
        for ds in barDatasets:
            # Extract category name from label (remove trailing " Spent" or " Income")
            let_cat = ds["label"].replace(" Spent", "").replace(" Income", "")
            ds["data"][-1] = next_data.get(let_cat, 0)
        # No prediction line is added.
    else:
        # No data for next month; compute prediction from the last 4 months.
        prediction = {}
        std = {}
        for cat, values in category_data.items():
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            prediction[cat] = mean_val
            std[cat] = math.sqrt(variance)
        for cat, values in category_data.items():
            color = stable_color(cat)
            lineData = [None] * len(values)
            lineData.append(prediction[cat])
            lineDatasets.append({
                "label": f"{cat} Predicted",
                "data": lineData,
                "borderColor": color,
                "fill": False,
                "type": "line"
            })
        # std can be returned if needed.
    
    # Append next month's label.
    labels.append(next_month_date.strftime('%b %Y'))

    return jsonify({
        "labels": labels,
        "barDatasets": barDatasets,
        "lineDatasets": lineDatasets,
        "std": {} if next_results else std
    })

# --- Data Page Routes ---
@app.route('/data/<month_year>')
def data_page(month_year):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    # Pass month_year as current_month and selected_month
    return render_template("data.html", current_month=month_year, selected_month=month_year, user=user)

@app.route('/data')
def data_default():
    default_month = date.today().strftime('%m-%Y')  # e.g., "03-2025" for March 2025
    return redirect(url_for('data_page', month_year=default_month))

# --------------------------
# Run the App
# --------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
