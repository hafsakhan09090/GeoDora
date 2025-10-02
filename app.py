from flask import Flask, render_template, request, abort
import sqlite3
import os
import json

app = Flask(__name__)

DB_FOLDER = "database"
DB_FILE = os.path.join(DB_FOLDER, "geography.db")

def get_db_connection():
    """Create a database connection with dictionary-style results."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    """Show list of countries, filtered by search if provided."""
    search_query = request.args.get('search', '').strip()
    conn = get_db_connection()

    if search_query:
        countries = conn.execute(
            "SELECT name, flag FROM countries WHERE name LIKE ? ORDER BY name",
            (f'%{search_query}%',)
        ).fetchall()
    else:
        countries = conn.execute("SELECT name, flag FROM countries ORDER BY name").fetchall()

    conn.close()
    return render_template("index.html", countries=countries, search_query=search_query)

@app.route("/country/<string:country_name>")
def country(country_name):
    """Show the details for a single country on its own page."""
    conn = get_db_connection()

    country_details = conn.execute("SELECT * FROM countries WHERE name = ?", (country_name,)).fetchone()

    if country_details is None:
        conn.close()
        abort(404) # Not found

    states = conn.execute(
        "SELECT name FROM states WHERE country_id = ? ORDER BY name",
        (country_details['id'],)
    ).fetchall()

    conn.close()

    # Convert languages from JSON string back to a Python list for the template
    country_dict = dict(country_details)
    try:
        country_dict['languages'] = json.loads(country_dict['languages'])
    except (json.JSONDecodeError, TypeError):
        country_dict['languages'] = []

    return render_template("country.html", country=country_dict, states=states)

if __name__ == "__main__":
    app.run(debug=True)
