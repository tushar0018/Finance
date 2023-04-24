import os
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd, lookdown

# Global variable
user_name = ""
userid = 0

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # user
    portfolio = db.execute("SELECT * FROM shares WHERE user_id = ?", userid)

    # add data in portfolio
    for x in portfolio:
        data = lookdown(x["symbol"])
        share = x["share"]

        # profit or loss
        old_price = share * x["price"]
        new_price = share * data["ltp"]
        gain = "{:.2f}".format(new_price - old_price)
        data["gain"] = float(gain)
        data["total"] = float(new_price)

        x.update(data)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", userid)

    return render_template("index.html", portfolio=portfolio, cash=cash)

    return apology("Tere Pass Itna Pesa H", 420)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Get the cash information of user
    cash = db.execute("SELECT cash FROM users WHERE username = ?", user_name)

    # method GET
    if request.method == "GET":
        return render_template("buy.html", cash=cash)

    # method POST
    if request.method == "POST":
        # to check symbol is correct or not
        data = lookup(request.form.get("symbol"))
        if data is None:
            return apology("Not Found")

        # date, symbol, number_share, price
        symbol = data["symbol"]
        now    = datetime.now()
        date = now.strftime("%Y-%m-%d %H:%M:%S")

        no_share = request.form.get("shares")
        price = data["price"]

        # check cases
        if not no_share.isdigit():
            try:
                if float(no_share).is_integer():
                    print("TRUE")
                    # return apology("provide integer value", 400)
                else:
                    return apology("String", 400)
            except:
                return apology("except", 400)

        if float(no_share) < 1.0:
            return apology("Less quantity", 400)

        total_value = float(no_share) * price
        # compare balance and total share value
        if (float(cash[0]["cash"]) < total_value):
            return apology("You don't have enough cash to buy shares! Add cash or decrease number of share")

        # remaining cash after buy share
        remaining_cash = int(float(cash[0]["cash"]) - total_value)

        # update database
        db.execute("UPDATE users SET cash = ? WHERE username = ?", remaining_cash, user_name)
        db.execute("INSERT INTO history (user_id, no_share, share_type, price, symbol, date) VALUES(?, ?, ?, ?, ?, ?)",
                   userid, no_share, "buy", price, symbol, date)

        # insert into share database
        row = db.execute("SELECT * FROM shares WHERE user_id = ? AND symbol = ?", userid, symbol)

        # if share is first buy
        if len(row) == 0:
            db.execute("INSERT INTO shares (user_id, symbol, share, price) VALUES(?, ?, ?, ?)",
                       userid, symbol, no_share, price)

        # we average price and add share update database
        else:
            old_price = row[0]["price"]
            old_share = row[0]["share"]
            total_share = old_share + int(no_share)
            # average price
            avg_price = ((float(old_share) * old_price) + total_value) / total_share
            avg = "{:.2f}".format(avg_price)
            avg_price = float(avg)

            # update database shares
            db.execute("UPDATE shares SET share = ?, price = ? WHERE user_id = ?", total_share, avg_price, userid)

        # redirect to index
        message = "Bought " + str(no_share) + " share of " + str(symbol) + " at price of " + str(price)
        flash(message)
        return redirect("/")

    return apology("try again", 100)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE user_id = ?", userid)

    # add company name
    for x in history:
        data = lookdown(x["symbol"])
        x["name"] = data["name"]

    return render_template("history.html", history=history)

    return apology("Histpry")


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
        global user_name
        user_name = request.form.get("username")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        global userid
        userid = rows[0]["id"]
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
    """Get stock quote."""
    
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        # Get the share data
        data = lookup(request.form.get("symbol"))
        
        #  if return is none
        if data == None:
            return apology("Sorry Not Found", 400)
        else:
            return render_template("quoted.html",data=data)
    


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # method GET
    if request.method == "GET":
        return render_template("register.html")

    # method POST
    if request.method == "POST":

        # check field
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide username", 400)

        # check the password is matched
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password Not Matched", 400)

        # hash the password
        password = request.form.get("confirmation")
        hash_password = generate_password_hash(password, "sha256")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Ensure username exists and password is correct
        if len(rows) != 0:
            return apology("user already exits", 400)

        # Insert username , password in database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), hash_password)

        flash("Registerd")
        return render_template("login.html")

    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get method
    if request.method == "GET":
        # get all stocks user have
        symbols = db.execute("SELECT symbol, share FROM shares WHERE user_id = ?", userid)
        return render_template("sell.html", symbols=symbols)

    # Post method
    if request.method == "POST":
        symbol = request.form.get("symbol")
        share = int(request.form.get("shares"))

        # check user input is valid or not
        if share < 1:
            return apology("share should be greater than 0")

        # check number of share in portfolio
        number_share = db.execute("SELECT share FROM shares WHERE user_id = ? AND symbol = ?", userid, symbol)
        if share > number_share[0]["share"]:
            return apology("share is greater than your holding")

        # update database
        db.execute("UPDATE shares SET share = share - ? WHERE user_id = ? AND symbol = ?", share, userid, symbol)

        # check whether number of share are then delete them from database
        check = db.execute("SELECT * FROM shares WHERE user_id = ? AND symbol = ?", userid, symbol)

        if int(check[0]["share"]) == 0:
            # db.execute("DELETE FROM shares WHERE user_id = ? AND symbol = ?", userid, symbol")
            db.execute("DELETE FROM shares WHERE user_id = ? AND symbol = ?", userid, symbol)

        # collect data
        data = lookup(symbol)
        price = data["price"]
        # date = data["date"]
        # xyz = data["da"]
        xyz = "2020-10-20"
        # now = datetime.now()
        # date = now.strftime("%Y-%m-%d %H:%M:%S")

        cash_after = round(float(share) * price)

        # update cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", cash_after, userid)
        db.execute("INSERT INTO history (user_id, no_share, share_type, price, symbol, date) VALUES(?, ?, ?, ?, ?, ?)",
                   userid, share, "sell", price, symbol, xyz)

        # redirect to index
        message = "Sold " + str(share) + " share of " + str(symbol) + " at price of " + str(price)
        flash(message)
        return redirect("/")

    return apology("SELL")


@app.route("/chart")
@login_required
def chart():
    symbol = request.args.get("symbol")

    portfolio = db.execute("SELECT * FROM shares WHERE user_id = ?", userid)

    for x in portfolio:
        data = lookdown(x["symbol"])
        share = x["share"]
        # profit or loss
        old_price = share * x["price"]
        new_price = share * data["ltp"]
        gain = "{:.2f}".format(new_price - old_price)
        data["gain"] = float(gain)
        x.update(data)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", userid)

    return render_template("chart.html", portfolio=portfolio, cash=cash, symbol=symbol)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():

    if request.method == "GET":
        info = db.execute("SELECT * FROM users WHERE id = ?", userid)
        return render_template("addcash.html", info=info)

    if request.method == "POST":
        cash = float(request.form.get("cash"))

        # check exceed limit
        if cash > 10000 and cash < 0:
            return apology("Fill correct info")

        # update database
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", cash, userid)

        # redirect index
        message = "$" + str(cash) + " Added to your Wallet!"
        flash(message)
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
