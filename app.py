import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
import time
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL(os.getenv("DATABASE_URI"))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")




@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    portfolio = db.execute("SELECT stock,SUM(shares) as quant FROM transactions WHERE user_id=? GROUP BY stock HAVING SUM(shares)>0", session["user_id"])
    full_portfolio = []
    values = []
    for row in portfolio:
        symbol = row['stock']
        shares = row['quant']
        info = lookup(symbol)
        name = info["name"]
        price = info["price"]
        value = shares*price
        values.append(value)
        full_portfolio.append({'Symbol':symbol, 'Name':name, 'Shares':shares, 'Price':price, 'Total':value})

    portfolio_value=sum(values)
    cash = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
    balance = cash[0]['cash']
    return render_template("index.html",full_portfolio=full_portfolio,portfolio_value=portfolio_value,balance=balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        stock = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not shares:
            return apology("PLEASE ENTER NUMBER OF SHARES")
        if not stock:
            return apology("NOT A VALID STOCK SYMBOL")

        res = lookup(stock)
        if not res:
            return apology("INAVLID SYMBOL")
        
        try:
            shares=float(shares)
            if int(shares) != shares or int(shares) <= 0:
                raise ValueError
            else:
                shares=int(shares)
        except ValueError:
            return apology("ENTER A VALID INTEGER NUMBER OF SHARES")

        price = res["price"]
        acc_balance = db.execute("SELECT cash FROM users WHERE id= ?",session["user_id"])

        if (shares*price > acc_balance[0]["cash"]):
            return apology("NOT ENOUGH FUNDS")

        new_balance = acc_balance[0]["cash"] - shares*price
        dy = str(datetime.date.today())
        t = str(time.strftime("%H:%M:%S", time.localtime()))


        db.execute("INSERT INTO transactions (user_id, stock, price, shares, date, time, type) VALUES (?,?,?,?,?,?,?)", session["user_id"],stock,price,shares,dy,t,"Buy")
        db.execute("UPDATE users SET cash=? WHERE id=?", new_balance, session["user_id"])


        return redirect("/")


@app.route("/history")
@login_required
def history():

    data = db.execute("SELECT stock,price,shares,date,time,type FROM transactions WHERE user_id = ?",session["user_id"])
    return render_template("history.html",data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "GET":
        return render_template("quote.html")
    else:
        res = lookup(request.form.get("symbol"))
        if res:
            name = res["name"]
            price = res["price"]
            symbol = res["symbol"]
            return render_template("quoted.html",name=name, price=price, symbol=symbol)
        else:
            return apology("INAVLID SYMBOL")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username"):
            return apology("Please provide a username")
        if not request.form.get("password"):
            return apology("Please provide a password")
        if not request.form.get("confirmation"):
            return apology("Please confirm password")

        username = request.form.get("username")
        password = request.form.get("password")

        #CHECKING IF USERNAME IS TAKEN
        if (len(db.execute("SELECT * FROM users WHERE username = ?",username)) != 0):
            return apology("Username unavailable")
        #CHECKING IF PASSWORDS DONOT MATCH
        if (request.form.get("password") != request.form.get("confirmation")):
            return apology("Passwords must match!")

        #ENTERING USERS INFO INTO DATABASE
        db.execute("INSERT INTO users (username,hash) VALUES (?,?)",username,generate_password_hash(password))
        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":

        stocks=db.execute("SELECT stock FROM transactions WHERE user_id=? GROUP BY stock HAVING SUM(shares)>0", session["user_id"])
        return render_template("sell.html",stocks=stocks)

    else:
        stock = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not stock:
            return apology("NOT A VALID STOCK SYMBOL")
        if not shares:
            return apology("ENTER NUMBER OF SHARES")

        try:
            shares=float(shares)
            if int(shares) != shares or int(shares) <= 0:
                raise ValueError
            else:
                shares=int(shares)
        except ValueError:
            return apology("ENTER A VALID INTEGER NUMBER OF SHARES")

        in_portfolio = db.execute("SELECT SUM(shares) AS quant FROM transactions WHERE stock=? AND user_id=? GROUP BY stock",stock,session["user_id"])
        amount_owned = in_portfolio[0]["quant"]

        if shares > amount_owned:
            return apology("NOT ENOUGH STOCKS OWNED")

        info = lookup(stock)
        current_price = info["price"]
        dy = str(datetime.date.today())
        t = str(time.strftime("%H:%M:%S", time.localtime()))
        acc_balance = db.execute("SELECT cash FROM users WHERE id= ?",session["user_id"])
        new_balance = acc_balance[0]["cash"] + (shares*current_price)
        shares=shares*-1

        db.execute("INSERT INTO transactions (user_id, stock, price, shares, date, time, type) VALUES (?,?,?,?,?,?,?)", session["user_id"],stock,current_price,shares,dy,t,"Sell")
        db.execute("UPDATE users SET cash=? WHERE id=?", new_balance, session["user_id"])

        return redirect("/")





