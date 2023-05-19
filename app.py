import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from time import strftime
from helpers import apology, login_required, lookup, usd

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
    # Query database to get a perticular user cash
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash_balance = user_cash[0]["cash"]

    # Select all activities done by a perticular user
    rows = db.execute("SELECT * FROM user WHERE user_id = ?", session["user_id"])

    grand_total = cash_balance

    for row in rows:
        quote = lookup(row["symbols"])
        total = row["shares"] * quote["price"]
        row.update({"price": quote["price"], "total": total})
        grand_total += total

    return render_template(
        "home/index.html", rows=rows, grand_total=grand_total, cash_balance=cash_balance
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Symbol/Shares field must not be empty!", 400)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a positive integer", 400)
        if shares < 1:
            return apology("shares must be a positive integer", 400)

        # Lookup the symbols price
        share_price = lookup(request.form.get("symbol"))

        # Checking if lookup returns none
        if share_price is None:
            return apology("Invalid symbol", 400)
        # Get the symbols price
        share_price = share_price["price"]

        # Calculate transaction cost
        total_cost = share_price * int(request.form.get("shares"))
        # pull out user cash
        user_cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"]
        )[0]["cash"]
        # pull out user shares
        curr_portfolio = db.execute(
            "SELECT shares FROM user WHERE symbols = :symbol AND user_id = :user_id",
            symbol=request.form.get("symbol"),
            user_id=session["user_id"],
        )
        # check if user has not bought the symbol before
        if not curr_portfolio:
            # check if user has enough fund
            if total_cost > user_cash:
                return apology("not enough balance", 400)
            # rmove the share cost from balance
            cash_balance = user_cash - total_cost

            # Take note of time of purchase
            date = strftime("%m/%d/%Y %H:%M")
            db.execute(
                "INSERT INTO history (id, symbols, price, stocks, date) VALUES (:id, :symbol, :price, :shares, :date)",
                id=session["user_id"],
                symbol=request.form.get("symbol"),
                price=lookup(request.form.get("symbol"))["price"],
                shares=shares,
                date=date,
            )

            # put the balance into the users database
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?",
                cash_balance,
                session["user_id"],
            )
            # push transaction details into database
            db.execute(
                "INSERT INTO user (user_id, symbols, name, shares, price, total) VALUES(:user_id, :symbol, :name, :shares, :price, :total)",
                user_id=session["user_id"],
                symbol=request.form.get("symbol"),
                name=lookup(request.form.get("symbol"))["name"],
                shares=int(request.form.get("shares")),
                price=lookup(request.form.get("symbol"))["price"],
                total=total_cost,
            )
        # if user has bought the stock before
        else:
            # Get the number of new shares
            new_share = int(request.form.get("shares"))

            # lookup the price for the share
            price = lookup(request.form.get("symbol"))["price"]

            # pull out the old number of share
            old_share = db.execute(
                "SELECT shares FROM user WHERE symbols = :symbol AND user_id = :user_id",
                symbol=request.form.get("symbol"),
                user_id=session["user_id"],
            )[0]["shares"]
            # Add to the old share
            total_shares = old_share + new_share

            # Calculate the new share price
            new_share_price = price * new_share
            # add the new share price to the old price of that same stock
            total_price = new_share_price + total_cost

            # pull out new user cash
            user_cash = db.execute(
                "SELECT cash FROM users WHERE id = ?", session["user_id"]
            )[0]["cash"]

            # check if user has enough fund
            if new_share_price > user_cash:
                return apology("not enough balance", 400)
            # remove the share price from the user cash
            new_cash_balance = user_cash - new_share_price

            # Take note of time of purchase
            date = strftime("%m/%d/%Y %H:%M")
            db.execute(
                "INSERT INTO history (id, symbols, price, stocks, date) VALUES (:id, :symbol, :price, :shares, :date)",
                id=session["user_id"],
                symbol=request.form.get("symbol"),
                price=lookup(request.form.get("symbol"))["price"],
                shares=shares,
                date=date,
            )

            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?",
                new_cash_balance,
                session["user_id"],
            )

            symbol = request.form.get("symbol")
            db.execute(
                "UPDATE user SET shares = ?, total = ? WHERE user_id = ? AND symbols = ?",
                total_shares,
                total_price,
                session["user_id"],
                symbol,
            )

        return redirect(url_for("index"))
    else:
        return render_template("shop/buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows1 = db.execute("SELECT * FROM history WHERE id = ?", session["user_id"])

    return render_template("shop/history.html", rows1=rows1)


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
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("accounts/login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect(url_for("index"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Confirm entered symbol
        quote = lookup(request.form.get("symbol"))
        if quote is None:
            return apology("Unknown symbol")
        return render_template(
            "price/quoted.html",
            name=quote["name"],
            symbol=quote["symbol"],
            price=quote["price"],
        )
    else:
        return render_template("price/quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        row = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username has not been taken
        if len(row) != 0:
            return apology("username has been taken")

        # Ensure form was correctly filled
        if not username:
            return apology("must provide username", 400)

        if not password:
            return apology("must provide password", 400)

        if not confirmation:
            return apology("must confirm password", 400)

        # Ensure password has been confirmed
        if password != confirmation:
            return apology("password mismatch", 400)

        password_hash = generate_password_hash(
            password, method="pbkdf2:sha256", salt_length=8
        )
        db.execute(
            "INSERT INTO users (username, hash) VALUES ( ?, ?)", username, password_hash
        )
        return redirect(url_for("index"))
    else:
        return render_template("accounts/register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("shares"):
            return apology("Missing shares", 400)

        if not request.form.get("symbol"):
            return apology("Missing symbol", 400)

        if int(request.form.get("shares")) < 1:
            return apology("Positive integer needed", 400)

        old_user_share = db.execute(
            "SELECT shares FROM user WHERE user_id = :id AND symbols=:symbol",
            id=session["user_id"],
            symbol=request.form.get("symbol"),
        )[0]["shares"]

        sold_share = int(request.form.get("shares"))

        if sold_share > old_user_share:
            return apology("Too many shares")

        share_price = lookup(request.form.get("symbol"))
        if share_price is None:
            return apology("Oops somthing went wrong")
        share_price = share_price["price"]

        # Take note of time of purchase
        date = strftime("%m/%d/%Y %H:%M")
        db.execute(
            "INSERT INTO history (id, symbols, price, stocks, date) VALUES (:id, :symbol, :price, :shares, :date)",
            id=session["user_id"],
            symbol=request.form.get("symbol"),
            price=lookup(request.form.get("symbol"))["price"],
            shares=sold_share * (-1),
            date=date,
        )

        sold_share_price = sold_share * share_price

        old_user_cash = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"]
        )[0]["cash"]

        new_user_cash = old_user_cash + sold_share_price

        new_user_share = old_user_share - sold_share
        # Updating user cash
        db.execute(
            "UPDATE users SET cash = :new_user_cash WHERE id = :id",
            id=session["user_id"],
            new_user_cash=new_user_cash,
        )

        # Updating user shares
        db.execute(
            "UPDATE user SET shares = :new_user_share WHERE user_id = :id AND symbols = :symbol",
            new_user_share=new_user_share,
            id=session["user_id"],
            symbol=request.form.get("symbol"),
        )

        if new_user_share == 0:
            db.execute(
                "DELETE FROM user WHERE user_id=:id AND symbols=:symbol",
                id=session["user_id"],
                symbol=request.form.get("symbol"),
            )
        return redirect(url_for("index"))
    else:
        rows = db.execute(
            "SELECT symbols FROM user WHERE user_id=:id", id=session["user_id"]
        )
        return render_template("shop/sell.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
