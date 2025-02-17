from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
import csv

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
    type = db.Column(db.String(20), nullable=False)  # e.g., 'bank' or 'credit'
    initial_balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(120))
    amount = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)  # computed field: previous balance + amount
    category = db.Column(db.String(80), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

# --------------------------
# Routes
# --------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

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
        bank_account = Account(name="Bank of America", type="bank", initial_balance=0.0, user_id=new_user.id)
        credit_account = Account(name="Discover", type="credit", initial_balance=0.0, user_id=new_user.id)
        db.session.add_all([bank_account, credit_account])
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

# --- Dashboard: Shows key values, list of transactions, add new transaction, filter/export ---
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    # Get optional date range filtering from query string
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    start_date = end_date = None
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except Exception as e:
            print("Date parsing error:", e)
    
    # Gather transactions for all the user's accounts
    transactions = []
    for account in user.accounts:
        query = Transaction.query.filter_by(account_id=account.id)
        if start_date and end_date:
            query = query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
        transactions += query.order_by(Transaction.date.asc(), Transaction.id.asc()).all()

    # Calculate totals per category
    category_totals = {}
    for txn in transactions:
        category_totals[txn.category] = category_totals.get(txn.category, 0) + txn.amount

    # Compute account balances (using the last transaction or initial balance)
    account_balances = {}
    for account in user.accounts:
        last_txn = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
        if last_txn:
            account_balances[account.name] = last_txn.balance
        else:
            account_balances[account.name] = account.initial_balance

    # Total balance: (sum of bank accounts) minus (sum of credit accounts)
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
                           start_date=start_date_str,
                           end_date=end_date_str)

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
    # Determine new balance: add amount to last balance (or account's initial balance)
    last_txn = Transaction.query.filter_by(account_id=account_id).order_by(Transaction.date.desc(), Transaction.id.desc()).first()
    if last_txn:
        new_balance = last_txn.balance + amount
    else:
        new_balance = account.initial_balance + amount

    new_txn = Transaction(date=txn_date,
                          description=description,
                          amount=amount,
                          balance=new_balance,
                          category=category,
                          account_id=account_id)
    db.session.add(new_txn)
    db.session.commit()
    return redirect(url_for('dashboard'))

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
        cw.writerow([txn.date.strftime('%Y-%m-%d'),
                     txn.account.name,
                     txn.description,
                     txn.amount,
                     txn.balance,
                     txn.category])
    
    output = si.getvalue()
    return send_file(
        io.BytesIO(output.encode('utf-8')),
        mimetype="text/csv",
        as_attachment=True,
        download_name="transactions.csv"
    )


# --------------------------
# Run the App
# --------------------------
if __name__ == '__main__':
    # Create tables if they don't exist (run once)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
