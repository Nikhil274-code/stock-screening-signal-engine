import sqlite3
import json

DB_PATH = "sensei_data.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Table for stock names
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_names (
                ticker TEXT PRIMARY KEY,
                name TEXT
            )
        """)

        # Table for AI rankings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rankings (
                ticker TEXT PRIMARY KEY,
                signal TEXT
            )
        """)

        # Table for stock info cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_info (
                ticker TEXT PRIMARY KEY,
                data TEXT
            )
        """)

        # Table for user watchlist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY
            )
        """)
        conn.commit()

def get_all_rankings():
    """Retrieves all AI rankings as a dictionary {ticker: signal}."""
    with get_connection() as conn:
        rows = conn.execute("SELECT ticker, signal FROM rankings").fetchall()
        return {row['ticker']: row['signal'] for row in rows}

def save_stock_name(ticker, name):
    """Saves or updates a company name for a given ticker."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO stock_names (ticker, name) VALUES (?, ?)",
            (ticker, name)
        )
        conn.commit()

def get_stock_name(ticker):
    """Retrieves the company name for a ticker, returning the ticker if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT name FROM stock_names WHERE ticker = ?",
            (ticker,)
        ).fetchone()
        return row['name'] if row else ticker

def save_rankings(rankings_dict):
    """Saves the global AI rankings to the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Clear old rankings first
        cursor.execute("DELETE FROM rankings")
        # Insert new rankings
        rankings_data = [(ticker, signal) for ticker, signal in rankings_dict.items()]
        cursor.executemany(
            "INSERT INTO rankings (ticker, signal) VALUES (?, ?)",
            rankings_data
        )
        conn.commit()

def get_watchlist():
    """Returns a list of tickers in the user's watchlist."""
    with get_connection() as conn:
        rows = conn.execute("SELECT ticker FROM watchlist").fetchall()
        return [row['ticker'] for row in rows]

def add_to_watchlist(ticker):
    """Adds a ticker to the user's watchlist."""
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (ticker,))
        conn.commit()

def remove_from_watchlist(ticker):
    """Removes a ticker from the user's watchlist."""
    with get_connection() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        conn.commit()

def save_stock_info(ticker, info_dict):
    """Saves company detailed info to the cache."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO stock_info (ticker, data) VALUES (?, ?)",
            (ticker, json.dumps(info_dict))
        )
        conn.commit()

def get_stock_info(ticker):
    """Retrieves company detailed info from the cache."""
    with get_connection() as conn:
        row = conn.execute("SELECT data FROM stock_info WHERE ticker = ?", (ticker,)).fetchone()
        return json.loads(row['data']) if row else None

# Initialize the DB on import
init_db()
