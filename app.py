from flask import Flask, render_template, request, jsonify, abort, session, redirect, url_for
import sqlite3
import os
import json
import random
from datetime import datetime
from urllib.parse import quote_plus, urlencode

app = Flask(__name__)
app.secret_key = 'geodora-secret-key-2024'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

DB_FILE = os.path.join(os.path.dirname(__file__), "geography.db")

# ===================== JINJA FILTERS =====================

@app.template_filter('format_int')
def format_int(value):
    """Format integer with commas."""
    try:
        if value is None or value == '':
            return "N/A"
        
        # Handle string values that might contain text
        if isinstance(value, str):
            import re
            # Remove all non-numeric characters except decimal points
            cleaned = re.sub(r'[^\d.]', '', value)
            if cleaned:
                # Try to convert to integer
                num = float(cleaned)
                if num.is_integer():
                    return f"{int(num):,}"
                else:
                    return f"{num:,.1f}"
            else:
                # If no numbers found, return original
                return value
        
        # Handle numbers directly
        num = float(value)
        if num.is_integer():
            return f"{int(num):,}"
        else:
            return f"{num:,.1f}"
    except (ValueError, TypeError):
        return str(value) if value else "N/A"

@app.template_filter('format_float')
def format_float(value):
    """Format float with commas and 1 decimal."""
    try:
        if value is None or value == '':
            return "N/A"
        if isinstance(value, str):
            import re
            numbers = re.findall(r'\d+\.?\d*', value)
            if numbers:
                value = float(numbers[0])
            else:
                return value
        return f"{float(value):,.1f}"
    except (ValueError, TypeError):
        return str(value) if value else "N/A"

@app.template_filter('format_area')
def format_area(value):
    """Format area with units."""
    try:
        if value is None or value == '':
            return "N/A"
        if isinstance(value, str):
            # Check if it already has units
            if 'km²' in value or 'km' in value:
                import re
                numbers = re.findall(r'\d+\.?\d*', value)
                if numbers:
                    area_num = float(numbers[0])
                    return f"{area_num:,.0f} km²"
                else:
                    return value
            else:
                import re
                numbers = re.findall(r'\d+\.?\d*', value)
                if numbers:
                    area_num = float(numbers[0])
                    return f"{area_num:,.0f} km²"
                else:
                    return f"{value} km²"
        return f"{float(value):,.0f} km²"
    except (ValueError, TypeError):
        return f"{value} km²" if value else "N/A"

@app.template_filter('extract_number')
def extract_number(value):
    """Extract first number from a string."""
    if value is None or value == '':
        return 0
    try:
        if isinstance(value, (int, float)):
            return float(value)
        import re
        numbers = re.findall(r'\d+\.?\d*', str(value))
        if numbers:
            return float(numbers[0])
        return 0
    except (ValueError, TypeError):
        return 0

@app.template_filter('urlencode')
def urlencode_filter(s):
    """URL encode a string."""
    return quote_plus(str(s))

# ===================== CONTEXT PROCESSORS =====================

@app.context_processor
def utility_processor():
    def update_url_param(param_name, param_value):
        """Update a single URL parameter."""
        args = request.args.copy()
        args[param_name] = param_value
        
        # Remove if it's default value
        if param_name == 'view' and param_value == 'list':
            args.pop('view', None)
        if param_name == 'sort' and param_value == 'name':
            args.pop('sort', None)
        if param_name == 'continent' and param_value == '':
            args.pop('continent', None)
        
        return f"?{urlencode(args)}" if args else ""
    
    return dict(update_url_param=update_url_param)

# ===================== HELPER FUNCTIONS =====================

def get_db_connection():
    """Create a database connection with dictionary-style results."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_table_columns(table_name):
    """Get all column names for a table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()
    return columns

def calculate_country_stats():
    """Calculate and cache country statistics."""
    conn = get_db_connection()
    
    stats = {
        'total_countries': 0,
        'total_population': 0,
        'largest_country': '',
        'smallest_country': '',
        'continents': {},
        'popular_countries': []
    }
    
    try:
        # Total countries
        cursor = conn.execute("SELECT COUNT(*) as count FROM countries")
        result = cursor.fetchone()
        stats['total_countries'] = result['count'] if result['count'] else 0
        
        # Total population (extract numbers from strings)
        cursor = conn.execute("SELECT population FROM countries WHERE population IS NOT NULL AND population != ''")
        total_pop = 0
        for row in cursor.fetchall():
            pop_str = row['population']
            if pop_str:
                try:
                    import re
                    numbers = re.findall(r'\d+\.?\d*', pop_str)
                    if numbers:
                        total_pop += float(numbers[0])
                except:
                    pass
        stats['total_population'] = total_pop
        
        # Largest and smallest by area
        cursor = conn.execute("SELECT name, area FROM countries WHERE area IS NOT NULL AND area != ''")
        countries_with_area = []
        for row in cursor.fetchall():
            name = row['name']
            area_str = row['area']
            if area_str:
                try:
                    import re
                    numbers = re.findall(r'\d+\.?\d*', area_str)
                    if numbers:
                        area_num = float(numbers[0])
                        countries_with_area.append({'name': name, 'area_num': area_num, 'area_str': area_str})
                except:
                    countries_with_area.append({'name': name, 'area_num': 0, 'area_str': area_str})
        
        if countries_with_area:
            # Sort by area number
            countries_with_area.sort(key=lambda x: x['area_num'], reverse=True)
            # Largest
            largest = countries_with_area[0]
            stats['largest_country'] = f"{largest['name']} ({largest['area_num']:,.0f} km²)" if largest['area_num'] > 0 else f"{largest['name']} ({largest['area_str']})"
            
            # Smallest (non-zero)
            non_zero = [c for c in countries_with_area if c['area_num'] > 0]
            if non_zero:
                smallest = min(non_zero, key=lambda x: x['area_num'])
                stats['smallest_country'] = f"{smallest['name']} ({smallest['area_num']:,.0f} km²)" if smallest['area_num'] > 0 else f"{smallest['name']} ({smallest['area_str']})"
        
        # Continents distribution
        cursor = conn.execute("SELECT region, COUNT(*) as count FROM countries WHERE region IS NOT NULL AND region != '' GROUP BY region")
        stats['continents'] = {row['region']: row['count'] for row in cursor.fetchall()}
        
    except Exception as e:
        print(f"Error calculating stats: {e}")
    
    # Popular countries (most visited in session)
    if 'visited_countries' in session:
        visited = session['visited_countries']
        if visited:
            try:
                placeholders = ','.join(['?'] * len(visited))
                cursor = conn.execute(
                    f"SELECT name, flag FROM countries WHERE name IN ({placeholders}) ORDER BY name",
                    visited
                )
                stats['popular_countries'] = [dict(row) for row in cursor.fetchall()]
            except:
                stats['popular_countries'] = []
    
    conn.close()
    return stats

def generate_country_facts(country):
    """Generate interesting facts about a country."""
    facts = []
    
    # Population fact
    if 'population' in country and country['population']:
        pop_num = extract_number(country['population'])
        if pop_num > 1000000000:
            facts.append(f"With over {format_population(pop_num)} people, it's one of the most populous countries.")
        elif pop_num < 1000000:
            facts.append(f"It has a small population of {format_population(pop_num)} people.")
        elif pop_num > 0:
            facts.append(f"It has a population of approximately {format_population(pop_num)} people.")
    
    # Area fact
    if 'area' in country and country['area']:
        area_num = extract_number(country['area'])
        if area_num > 5000000:
            facts.append(f"Covering {format_area(area_num)}, it's one of the largest countries by land area.")
        elif area_num < 1000:
            facts.append(f"With an area of just {format_area(area_num)}, it's one of the smallest countries.")
        elif area_num > 0:
            facts.append(f"It spans an area of {format_area(area_num)}.")
    
    # Capital fact
    if 'capital' in country and country['capital']:
        facts.append(f"The capital city is {country['capital']}.")
    
    # Region fact
    if 'region' in country and country['region']:
        facts.append(f"It's located in {country['region']}.")
    
    # Government fact
    if 'democracy_type' in country and country['democracy_type']:
        facts.append(f"It has a {country['democracy_type'].lower()} form of government.")
    
    # Currency fact
    if 'currency' in country and country['currency']:
        facts.append(f"The official currency is the {country['currency']}.")
    
    # Add some random interesting facts
    interesting_facts = [
        "This country has a rich cultural heritage with influences from various civilizations.",
        "It's known for its unique geographical features and diverse ecosystems.",
        "The country has made significant contributions to science, art, and literature.",
        "It has a fascinating history that spans centuries of development.",
        "The local cuisine is renowned for its unique flavors and traditional dishes."
    ]
    
    if len(facts) < 5:
        facts.append(random.choice(interesting_facts))
    
    return facts[:5]

def calculate_comparisons(countries):
    """Calculate comparison metrics between countries."""
    comparisons = {
        'population': {'max': 0, 'min': float('inf'), 'avg': 0},
        'area': {'max': 0, 'min': float('inf'), 'avg': 0},
    }
    
    total_pop = 0
    total_area = 0
    count = len(countries)
    
    for country in countries:
        pop = country.get('population', 0) or 0
        area = country.get('area', 0) or 0
        
        pop_num = extract_number(pop)
        area_num = extract_number(area)
        
        comparisons['population']['max'] = max(comparisons['population']['max'], pop_num)
        comparisons['population']['min'] = min(comparisons['population']['min'], pop_num)
        total_pop += pop_num
        
        comparisons['area']['max'] = max(comparisons['area']['max'], area_num)
        comparisons['area']['min'] = min(comparisons['area']['min'], area_num)
        total_area += area_num
    
    if count > 0:
        comparisons['population']['avg'] = total_pop / count
        comparisons['area']['avg'] = total_area / count
    
    return comparisons

def format_population(population):
    """Format population with commas."""
    try:
        if isinstance(population, str):
            pop_num = extract_number(population)
            return f"{pop_num:,.0f}"
        return f"{float(population):,.0f}"
    except (ValueError, TypeError):
        return str(population) if population else "N/A"

def format_area(area):
    """Format area with commas and units."""
    try:
        if isinstance(area, str):
            area_num = extract_number(area)
            return f"{area_num:,.0f} km²"
        return f"{float(area):,.0f} km²"
    except (ValueError, TypeError):
        return f"{area} km²" if area else "N/A"

# ===================== ROUTES =====================

@app.route("/")
def index():
    """Show list of countries with filtering and sorting."""
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'name')
    continent = request.args.get('continent', '')
    view_mode = request.args.get('view', 'list')
    
    conn = get_db_connection()
    
    # Build query - only select columns that exist
    country_columns = get_table_columns('countries')
    
    # Always include these basic columns
    select_fields = ["id", "name", "flag"]
    
    # Add optional columns if they exist
    optional_cols = ['region', 'population', 'area', 'capital']
    for col in optional_cols:
        if col in country_columns:
            select_fields.append(col)
    
    query = f"SELECT {', '.join(select_fields)} FROM countries WHERE 1=1"
    params = []
    
    if search_query:
        search_conditions = ["name LIKE ?"]
        params.append(f'%{search_query}%')
        
        if 'region' in country_columns:
            search_conditions.append("region LIKE ?")
            params.append(f'%{search_query}%')
        
        if 'capital' in country_columns:
            search_conditions.append("capital LIKE ?")
            params.append(f'%{search_query}%')
        
        query += " AND (" + " OR ".join(search_conditions) + ")"
    
    if continent and 'region' in country_columns:
        query += " AND region = ?"
        params.append(continent)
    
    # Sorting options based on available columns
    sort_options = {
        'name': 'name ASC',
        'name_desc': 'name DESC',
    }
    
    # Add population sorting if column exists
    if 'population' in country_columns:
        sort_options['pop_high'] = 'population DESC, name ASC'
        sort_options['pop_low'] = 'population ASC, name ASC'
    
    # Add area sorting if column exists
    if 'area' in country_columns:
        sort_options['area_high'] = 'area DESC, name ASC'
        sort_options['area_low'] = 'area ASC, name ASC'
    
    # Add region sorting if column exists
    if 'region' in country_columns:
        sort_options['region'] = 'region ASC, name ASC'
    
    query += f" ORDER BY {sort_options.get(sort_by, 'name ASC')}"
    
    countries = conn.execute(query, params).fetchall()
    
    # Get continents for filter dropdown
    continents = []
    if 'region' in country_columns:
        continents = conn.execute(
            "SELECT DISTINCT region FROM countries WHERE region IS NOT NULL AND region != '' ORDER BY region"
        ).fetchall()
    
    # Get country statistics
    stats = calculate_country_stats()
    
    # Get random country for "Country of the Day"
    random_country = conn.execute(
        "SELECT name, flag FROM countries ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    
    conn.close()
    
    return render_template("index.html", 
                         countries=countries, 
                         search_query=search_query,
                         continents=continents,
                         current_sort=sort_by,
                         current_continent=continent,
                         view_mode=view_mode,
                         stats=stats,
                         random_country=random_country)

@app.route("/country/<string:country_name>")
def country(country_name):
    """Show detailed information for a specific country."""
    # Track visited countries in session
    if 'visited_countries' not in session:
        session['visited_countries'] = []
    
    if country_name not in session['visited_countries']:
        session['visited_countries'].append(country_name)
        if len(session['visited_countries']) > 10:
            session['visited_countries'] = session['visited_countries'][-10:]
        session.modified = True
    
    conn = get_db_connection()
    
    country_details = conn.execute(
        "SELECT * FROM countries WHERE name = ?", 
        (country_name,)
    ).fetchone()
    
    if not country_details:
        conn.close()
        return render_template('404.html', country_name=country_name), 404
    
    # Get states/provinces - states table only has name
    states = conn.execute(
        "SELECT name FROM states WHERE country_id = ? ORDER BY name",
        (country_details['id'],)
    ).fetchall()
    
    # Get bordering countries - check if borders column exists
    borders = []
    country_dict = dict(country_details)
    
    # Check for borders column
    country_columns = get_table_columns('countries')
    if 'borders' in country_columns and 'borders' in country_dict and country_dict['borders']:
        border_data = country_dict['borders']
        try:
            border_ids = json.loads(border_data)
            if border_ids:
                placeholders = ','.join(['?'] * len(border_ids))
                borders = conn.execute(
                    f"SELECT name, flag FROM countries WHERE id IN ({placeholders}) ORDER BY name",
                    border_ids
                ).fetchall()
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Get similar countries (same region)
    similar_countries = []
    if 'region' in country_dict and country_dict['region']:
        similar_countries = conn.execute(
            "SELECT name, flag, capital FROM countries WHERE region = ? AND name != ? ORDER BY RANDOM() LIMIT 4",
            (country_dict['region'], country_dict['name'])
        ).fetchall()
    
    # Get country facts/trivia
    facts = generate_country_facts(country_dict)
    
    conn.close()
    
    # Process data for template
    if 'languages' in country_dict and country_dict['languages']:
        try:
            country_dict['languages'] = json.loads(country_dict['languages'])
        except (json.JSONDecodeError, TypeError):
            country_dict['languages'] = []
    else:
        country_dict['languages'] = []
    
    return render_template("country.html", 
                         country=country_dict, 
                         states=states,
                         borders=borders,
                         similar_countries=similar_countries,
                         facts=facts)

@app.route("/compare")
def compare_countries():
    """Compare multiple countries."""
    countries_param = request.args.get('countries', '')
    if not countries_param:
        return redirect(url_for('index'))
    
    countries_list = countries_param.split(',')
    if len(countries_list) < 2:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # Get countries data
    placeholders = ','.join(['?'] * len(countries_list))
    countries = conn.execute(
        f"SELECT * FROM countries WHERE name IN ({placeholders})",
        countries_list
    ).fetchall()
    
    if len(countries) < 2:
        conn.close()
        return redirect(url_for('index'))
    
    conn.close()
    
    # Process each country
    countries_data = []
    for country in countries:
        country_dict = dict(country)
        if 'languages' in country_dict and country_dict['languages']:
            try:
                country_dict['languages'] = json.loads(country_dict['languages'])
            except:
                country_dict['languages'] = []
        else:
            country_dict['languages'] = []
        countries_data.append(country_dict)
    
    # Calculate comparisons
    comparisons = calculate_comparisons(countries_data)
    
    return render_template("compare.html",
                         countries=countries_data,
                         comparisons=comparisons)

@app.route("/quiz")
def quiz():
    """Interactive geography quiz."""
    quiz_type = request.args.get('type', 'capitals')
    difficulty = request.args.get('difficulty', 'easy')
    
    # Set number of questions based on difficulty
    if difficulty == 'easy':
        num_questions = 10
    elif difficulty == 'medium':
        num_questions = 15
    else:  # hard
        num_questions = 20
    
    conn = get_db_connection()
    
    if quiz_type == 'capitals':
        # Capital cities quiz
        questions = conn.execute("""
            SELECT name, capital, flag FROM countries 
            WHERE capital IS NOT NULL AND capital != ''
            ORDER BY RANDOM() LIMIT ?
        """, (num_questions,)).fetchall()
        
        quiz_data = []
        for question in questions:
            wrong_capitals = conn.execute("""
                SELECT capital FROM countries 
                WHERE capital != ? AND capital IS NOT NULL AND capital != ''
                ORDER BY RANDOM() LIMIT 3
            """, (question['capital'],)).fetchall()
            
            options = [question['capital']] + [w['capital'] for w in wrong_capitals]
            random.shuffle(options)
            
            quiz_data.append({
                'country': question['name'],
                'flag': question['flag'],
                'correct_answer': question['capital'],
                'options': options
            })
    
    elif quiz_type == 'flags':
        # Flag identification quiz
        questions = conn.execute("""
            SELECT name, flag FROM countries 
            ORDER BY RANDOM() LIMIT ?
        """, (num_questions,)).fetchall()
        
        quiz_data = []
        for question in questions:
            wrong_countries = conn.execute("""
                SELECT name FROM countries 
                WHERE name != ? 
                ORDER BY RANDOM() LIMIT 3
            """, (question['name'],)).fetchall()
            
            options = [question['name']] + [w['name'] for w in wrong_countries]
            random.shuffle(options)
            
            quiz_data.append({
                'flag': question['flag'],
                'correct_answer': question['name'],
                'options': options
            })
    
    else:  # general knowledge
        questions = conn.execute("""
            SELECT name, capital, population, area, region, flag FROM countries 
            ORDER BY RANDOM() LIMIT ?
        """, (num_questions,)).fetchall()
        
        quiz_data = []
        for question in questions:
            q_types = [
                ('capital', f"What is the capital of {question['name']}?", question['capital']),
                ('continent', f"Which continent is {question['name']} in?", question['region']),
            ]
            
            # Add population question if data exists
            if question['population']:
                q_types.append(('population', f"What is the approximate population of {question['name']}?", 
                               format_population(question['population'])))
            
            # Add area question if data exists
            if question['area']:
                q_types.append(('area', f"What is the approximate area of {question['name']}?", 
                               format_area(question['area'])))
            
            if not q_types:
                continue
                
            q_type, q_text, correct_answer = random.choice(q_types)
            
            # Generate wrong answers
            if q_type == 'capital':
                wrong_answers = conn.execute("""
                    SELECT capital FROM countries 
                    WHERE capital != ? AND capital IS NOT NULL AND capital != ''
                    ORDER BY RANDOM() LIMIT 3
                """, (correct_answer,)).fetchall()
                options = [correct_answer] + [w['capital'] for w in wrong_answers]
                
            elif q_type == 'continent':
                wrong_answers = conn.execute("""
                    SELECT DISTINCT region FROM countries 
                    WHERE region != ? AND region IS NOT NULL AND region != ''
                    ORDER BY RANDOM() LIMIT 3
                """, (correct_answer,)).fetchall()
                options = [correct_answer] + [w['region'] for w in wrong_answers]
                
            else:  # population or area
                if q_type == 'population' and question['population']:
                    try:
                        pop = extract_number(question['population'])
                        options = [
                            format_population(pop),
                            format_population(int(pop * 0.5)),
                            format_population(int(pop * 2)),
                            format_population(int(pop * 0.8))
                        ]
                    except (ValueError, TypeError):
                        continue
                elif q_type == 'area' and question['area']:
                    try:
                        area = extract_number(question['area'])
                        options = [
                            format_area(area),
                            format_area(int(area * 0.6)),
                            format_area(int(area * 1.5)),
                            format_area(int(area * 0.9))
                        ]
                    except (ValueError, TypeError):
                        continue
                else:
                    continue
                
                random.shuffle(options)
                correct_answer = options[0]
            
            random.shuffle(options)
            
            quiz_data.append({
                'country': question['name'],
                'flag': question['flag'],
                'question': q_text,
                'correct_answer': correct_answer,
                'options': options,
                'type': q_type
            })
    
    conn.close()
    
    return render_template("quiz.html",
                         quiz_data=quiz_data,
                         quiz_type=quiz_type,
                         difficulty=difficulty)

@app.route("/api/countries")
def api_countries():
    """JSON API endpoint for countries data."""
    conn = get_db_connection()
    
    countries = conn.execute("""
        SELECT name, flag, region, capital, population, area 
        FROM countries 
        ORDER BY name
    """).fetchall()
    
    conn.close()
    
    return jsonify([dict(country) for country in countries])

@app.route("/api/country/<string:country_name>")
def api_country(country_name):
    """JSON API endpoint for specific country."""
    conn = get_db_connection()
    
    country = conn.execute(
        "SELECT * FROM countries WHERE name = ?", 
        (country_name,)
    ).fetchone()
    
    if not country:
        conn.close()
        return jsonify({"error": "Country not found"}), 404
    
    conn.close()
    
    country_dict = dict(country)
    try:
        country_dict['languages'] = json.loads(country_dict['languages'])
    except:
        country_dict['languages'] = []
    
    return jsonify(country_dict)

@app.route("/stats")
def statistics():
    """Show statistics and analytics."""
    stats = calculate_country_stats()
    
    conn = get_db_connection()
    
    # Get top 10 most populous countries
    top_populous_raw = conn.execute("""
        SELECT name, flag, population 
        FROM countries 
        WHERE population IS NOT NULL AND population != ''
        ORDER BY name
    """).fetchall()
    
    # Extract numbers and sort
    top_populous = []
    for country in top_populous_raw:
        top_populous.append({
            'name': country['name'],
            'flag': country['flag'],
            'population': country['population'],
            'population_num': extract_number(country['population'])
        })
    
    # Sort by population number
    top_populous.sort(key=lambda x: x['population_num'], reverse=True)
    top_populous = top_populous[:10]
    
    # Get top 10 largest by area
    top_area_raw = conn.execute("""
        SELECT name, flag, area 
        FROM countries 
        WHERE area IS NOT NULL AND area != ''
        ORDER BY name
    """).fetchall()
    
    top_area = []
    for country in top_area_raw:
        top_area.append({
            'name': country['name'],
            'flag': country['flag'],
            'area': country['area'],
            'area_num': extract_number(country['area'])
        })
    
    # Sort by area number
    top_area.sort(key=lambda x: x['area_num'], reverse=True)
    top_area = top_area[:10]
    
    # Get continent statistics
    continent_stats_raw = conn.execute("""
        SELECT region, 
               COUNT(*) as country_count
        FROM countries 
        WHERE region IS NOT NULL AND region != ''
        GROUP BY region
        ORDER BY country_count DESC
    """).fetchall()
    
    # Convert continent stats to list of dicts
    continent_stats = []
    for row in continent_stats_raw:
        continent_stats.append({
            'region': row['region'],
            'country_count': row['country_count'],
            'total_population': 0,
            'total_area': 0
        })
    
    # Try to get population and area totals for each continent
    for continent in continent_stats:
        pop_result = conn.execute("""
            SELECT SUM(CAST(SUBSTR(population, 1, INSTR(population || ' ', ' ')) AS INTEGER)) as total_pop
            FROM countries 
            WHERE region = ? AND population IS NOT NULL AND population != ''
        """, (continent['region'],)).fetchone()
        
        area_result = conn.execute("""
            SELECT SUM(CAST(SUBSTR(area, 1, INSTR(area || ' ', ' ')) AS INTEGER)) as total_area
            FROM countries 
            WHERE region = ? AND area IS NOT NULL AND area != ''
        """, (continent['region'],)).fetchone()
        
        if pop_result and pop_result['total_pop']:
            continent['total_population'] = pop_result['total_pop']
        if area_result and area_result['total_area']:
            continent['total_area'] = area_result['total_area']
    
    conn.close()
    
    return render_template("stats.html",
                         stats=stats,
                         top_populous=top_populous,
                         top_area=top_area,
                         continent_stats=continent_stats)

@app.route("/about")
def about():
    """About page."""
    stats = calculate_country_stats()
    return render_template("about.html", stats=stats)

# ===================== ERROR HANDLERS =====================

@app.errorhandler(404)
def page_not_found(e):
    country_name = request.args.get('country_name', '')
    return render_template('404.html', country_name=country_name), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# ===================== MAIN =====================

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)