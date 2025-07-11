from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'hospital-secret-key'

# 初始化資料庫
def init_db():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        id_number TEXT,
        birthday TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        department TEXT,
        symptoms TEXT,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_status (
        id INTEGER PRIMARY KEY,
        allow_register INTEGER
    )''')
    c.execute("INSERT OR IGNORE INTO system_status (id, allow_register) VALUES (1, 1)")
    conn.commit()
    conn.close()

init_db()

# 註冊頁
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        id_number = request.form['id_number']
        birthday = request.form['birthday']
        conn = sqlite3.connect('hospital.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, id_number, birthday) VALUES (?, ?, ?, ?)",
                      (username, password, id_number, birthday))
            conn.commit()
            return redirect('/login')
        except:
            return "❌ 帳號已存在"
        finally:
            conn.close()
    return render_template('register.html')

# 登入頁
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('hospital.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect('/')
        else:
            return "❌ 帳號或密碼錯誤"
    return render_template('login.html')

# 病人主頁
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute("SELECT allow_register FROM system_status WHERE id=1")
    status = c.fetchone()[0]

    if request.method == 'POST' and status == 1:
        department = request.form['department']
        symptoms = request.form['symptoms']
        c.execute("INSERT INTO appointments (user_id, department, symptoms, status) VALUES (?, ?, ?, ?)",
                  (session['user_id'], department, symptoms, 'waiting'))
        conn.commit()
        conn.close()
        return "✅ 掛號成功！請等候叫號"
    
    return render_template('patient_home.html', allow_register=status)

# 醫生端
@app.route('/doctor', methods=['GET', 'POST'])
def doctor():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()

    if request.method == 'POST':
        if 'stop' in request.form:
            c.execute("UPDATE system_status SET allow_register=0 WHERE id=1")
        elif 'resume' in request.form:
            c.execute("UPDATE system_status SET allow_register=1 WHERE id=1")
        elif 'next' in request.form:
            c.execute("SELECT id FROM appointments WHERE status='waiting' ORDER BY id ASC LIMIT 1")
            next_patient = c.fetchone()
            if next_patient:
                c.execute("UPDATE appointments SET status='called' WHERE id=?", (next_patient[0],))
        conn.commit()

    c.execute('''SELECT a.id, u.username, a.department, a.symptoms
                 FROM appointments a JOIN users u ON a.user_id = u.id
                 WHERE a.status = 'waiting'
                 ORDER BY a.id ASC''')
    waiting_list = c.fetchall()
    conn.close()
    return render_template('doctor_home.html', waiting=waiting_list)
