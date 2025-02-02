from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the database
def init_db():
    with sqlite3.connect('database1.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                Username TEXT,
                Email TEXT,
                Password TEXT,
                PRIMARY KEY (Username, Email)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Recipes (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT,
                Name TEXT,
                Ingredients TEXT,
                Process TEXT,
                Cost REAL,
                Rating REAL,
                Photo TEXT,
                FOREIGN KEY (Username) REFERENCES Users(Username)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Comments (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                RecipeID INTEGER,
                Username TEXT,
                Comment TEXT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (RecipeID) REFERENCES Recipes(ID),
                FOREIGN KEY (Username) REFERENCES Users(Username)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Cart (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT,
                RecipeID INTEGER,
                Quantity INTEGER,
                FOREIGN KEY (Username) REFERENCES Users(Username),
                FOREIGN KEY (RecipeID) REFERENCES Recipes(ID)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Orders (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT,
                RecipeID INTEGER,
                Quantity INTEGER,
                OrderDate DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Username) REFERENCES Users(Username),
                FOREIGN KEY (RecipeID) REFERENCES Recipes(ID)
            )
        ''')

        # Ensure that the Timestamp column exists in the Comments table
        try:
            conn.execute("SELECT Timestamp FROM Comments LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE Comments ADD COLUMN Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")

init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        with sqlite3.connect('database1.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Username, Password FROM Users WHERE Email = ?", (email,))
            user = cursor.fetchone()

            if user and user[1] == password:
                session['user'] = user[0]
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid email or password'

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('registerUsername')
        email = request.form.get('registerEmail')
        password = request.form.get('registerPassword')

        if username and email and password:
            with sqlite3.connect('database1.db') as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO Users (Username, Email, Password) VALUES (?, ?, ?)", (username, email, password))
                    conn.commit()
                    return redirect(url_for('login'))
                except sqlite3.IntegrityError:
                    error = 'Username and email combination already exists.'
        else:
            error = 'Please fill out all fields'

    return render_template("register.html", error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    username = session['user']
    search_query = request.args.get('search_query')
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        
        if search_query:
            cursor.execute("SELECT ID, Name, Photo, Rating FROM Recipes WHERE Name LIKE ?", ('%' + search_query + '%',))
        else:
            cursor.execute("SELECT ID, Name, Photo, Rating FROM Recipes")
        
        recipes = cursor.fetchall()
    
    return render_template("home.html", user=username, recipes=recipes)

@app.route('/user_recipes')
def user_recipes():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ID, Name, Photo, Rating FROM Recipes WHERE Username = ?", (username,))
        recipes = cursor.fetchall()

    return render_template("user_recipes.html", user=username, recipes=recipes)

@app.route('/recipe/<int:recipe_id>', methods=['GET', 'POST'])
def recipe_detail(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        comment_text = request.form.get('comment')
        username = session['user']
        with sqlite3.connect('database1.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Comments (RecipeID, Username, Comment) VALUES (?, ?, ?)",
                           (recipe_id, username, comment_text))
            conn.commit()
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Ingredients, Process, Cost, Rating, Photo, Username FROM Recipes WHERE ID = ?", (recipe_id,))
        recipe = cursor.fetchone()
        
        cursor.execute("SELECT Username, Comment, Timestamp FROM Comments WHERE RecipeID = ? ORDER BY Timestamp DESC", (recipe_id,))
        comments = cursor.fetchall()
    
    if not recipe:
        return "Recipe not found", 404

    owner = recipe[6]  # Get the owner's username
    return render_template("recipe_detail.html", recipe=recipe, recipe_id=recipe_id, comments=comments, owner=owner)

@app.route('/add_recipe', methods=['GET', 'POST'])
def add_recipe():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        recipe_name = request.form.get('recipeName')
        recipe_ingredients = request.form.get('ingredients')
        recipe_process = request.form.get('process')
        recipe_cost = request.form.get('cost')
        recipe_rating = request.form.get('rating')
        recipe_photo = request.files['recipeImage']

        if recipe_photo and allowed_file(recipe_photo.filename):
            filename = secure_filename(recipe_photo.filename)
            unique_filename = f"{recipe_name}_{filename}"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            recipe_photo.save(photo_path)

            with sqlite3.connect('database1.db') as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Recipes (Username, Name, Ingredients, Process, Cost, Rating, Photo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (session['user'], recipe_name, recipe_ingredients, recipe_process, recipe_cost, recipe_rating, photo_path))
                conn.commit()
            
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid file format. Please upload an image file.')
    
    return render_template('add_recipe.html')

@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT Username FROM Recipes WHERE ID = ?", (recipe_id,))
        recipe_owner = cursor.fetchone()
        
        if not recipe_owner or recipe_owner[0] != session['user']:
            return redirect(url_for('dashboard'))  # Redirect if not the owner

        if request.method == 'POST':
            recipe_name = request.form.get('recipeName')
            recipe_ingredients = request.form.get('ingredients')
            recipe_process = request.form.get('process')
            recipe_cost = request.form.get('cost')
            recipe_rating = request.form.get('rating')
            recipe_photo = request.files.get('recipeImage')

            if recipe_photo and allowed_file(recipe_photo.filename):
                filename = secure_filename(recipe_photo.filename)
                unique_filename = f"{recipe_name}_{filename}"
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                recipe_photo.save(photo_path)

                cursor.execute("UPDATE Recipes SET Name = ?, Ingredients = ?, Process = ?, Cost = ?, Rating = ?, Photo = ? WHERE ID = ?",
                               (recipe_name, recipe_ingredients, recipe_process, recipe_cost, recipe_rating, photo_path, recipe_id))
            else:
                cursor.execute("UPDATE Recipes SET Name = ?, Ingredients = ?, Process = ?, Cost = ?, Rating = ? WHERE ID = ?",
                               (recipe_name, recipe_ingredients, recipe_process, recipe_cost, recipe_rating, recipe_id))

            conn.commit()
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))

        cursor.execute("SELECT Name, Ingredients, Process, Cost, Rating, Photo FROM Recipes WHERE ID = ?", (recipe_id,))
        recipe = cursor.fetchone()
        
        if not recipe:
            return "Recipe not found", 404

    return render_template('edit_recipe.html', recipe=recipe, recipe_id=recipe_id)

@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM Recipes WHERE ID = ? AND Username = ?", (recipe_id, username))
        conn.commit()

    return redirect(url_for('user_recipes'))

@app.route('/add_to_cart/<int:recipe_id>', methods=['POST'])
def add_to_cart(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    quantity = int(request.form.get('quantity', 1))
    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ID FROM Cart WHERE RecipeID = ? AND Username = ?", (recipe_id, username))
        cart_item = cursor.fetchone()
        
        if cart_item:
            cursor.execute("UPDATE Cart SET Quantity = Quantity + ? WHERE ID = ?", (quantity, cart_item[0]))
        else:
            cursor.execute("INSERT INTO Cart (Username, RecipeID, Quantity) VALUES (?, ?, ?)", (username, recipe_id, quantity))
        
        conn.commit()

    return redirect(url_for('view_cart'))

@app.route('/view_cart')
def view_cart():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Cart.ID, Recipes.Name, Recipes.Cost, Recipes.Photo, Cart.Quantity
            FROM Cart
            JOIN Recipes ON Cart.RecipeID = Recipes.ID
            WHERE Cart.Username = ?
        """, (username,))
        cart_items = cursor.fetchall()

    total_cost = sum(item[2] * item[4] for item in cart_items)
    discount = total_cost * 0.1 if total_cost > 20 else 0
    final_cost = total_cost - discount

    return render_template('view_cart.html', cart_items=cart_items, total_cost=total_cost, discount=discount, final_cost=final_cost)

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT RecipeID, Quantity
            FROM Cart
            WHERE Username = ?
        """, (username,))
        cart_items = cursor.fetchall()

        for item in cart_items:
            cursor.execute("INSERT INTO Orders (Username, RecipeID, Quantity) VALUES (?, ?, ?)", (username, item[0], item[1]))

        cursor.execute("DELETE FROM Cart WHERE Username = ?", (username,))
        conn.commit()

    flash('Your order has been placed successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/view_orders')
def view_orders():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    
    with sqlite3.connect('database1.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Orders.ID, Recipes.Name, Recipes.Cost, Orders.Quantity, Orders.OrderDate
            FROM Orders
            JOIN Recipes ON Orders.RecipeID = Recipes.ID
            WHERE Orders.Username = ?
        """, (username,))
        orders = cursor.fetchall()

    return render_template('view_orders.html', orders=orders)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
