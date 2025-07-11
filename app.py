# 完整升級版：醫院掛號系統 app.py
# 功能：角色權限、掛號查詢、取消掛號、叫號顯示、醫生註冊需經審核、UI提示與假資料匯入

from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'hospital-secret-key'

# 資料庫初始化

def init_db():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        id_number TEXT,
        birthday TEXT,
        role TEXT DEFAULT 'patient',
        approved INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        department TEXT,
        symptoms TEXT,
        status TEXT,
        timestamp DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_status (
        id INTEGER PRIMARY KEY,
        allow_register INTEGER,
        current_number INTEGER
    )''')
    c.execute("INSERT OR IGNORE INTO system_status (id, allow_register, current_number) VALUES (1, 1, 0)")

    # 匯入假帳號（一次性）
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, id_number, birthday, role, approved) VALUES (?, ?, ?, ?, ?, 1)",
                  ("patient1", "1234", "A123456789", "2000-01-01", "patient"))
        c.execute("INSERT INTO users (username, password, id_number, birthday, role, approved) VALUES (?, ?, ?, ?, ?, 1)",
                  ("doctor1", "1234", "B234567890", "1980-01-01", "doctor"))
    conn.commit()
    conn.close()

init_db()

# 權限檢查裝飾器

def login_required(role=None):
    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            conn = sqlite3.connect('hospital.db')
            c = conn.cursor()
            c.execute("SELECT role, approved FROM users WHERE id=?", (session['user_id'],))
            result = c.fetchone()
            conn.close()
            if not result:
                return redirect('/login')
            user_role, approved = result
            if role and user_role != role:
                flash("⛔ 權限不足")
                return redirect('/')
            if user_role == 'doctor' and not approved:
                flash("⛔ 醫師帳號尚未審核通過")
                return redirect('/')
            return func(*args, **kwargs)
        return decorated_view
    return wrapper

# 註冊
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        id_number = request.form['id_number']
        birthday = request.form['birthday']
        role = request.form['role']
        approved = 0 if role == 'doctor' else 1
        conn = sqlite3.connect('hospital.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, id_number, birthday, role, approved) VALUES (?, ?, ?, ?, ?, ?)",
                      (username, password, id_number, birthday, role, approved))
            conn.commit()
            flash("✅ 註冊成功，請登入")
            return redirect('/login')
        except:
            flash("❌ 帳號已存在")
        finally:
            conn.close()
    return render_template('register.html')

# 登入
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
            flash("✅ 登入成功")
            return redirect('/')
        else:
            flash("❌ 帳號或密碼錯誤")
    return render_template('login.html')

# 登出
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("🚪 已登出")
    return redirect('/login')

# 病人首頁（掛號＋紀錄＋取消）
@app.route('/', methods=['GET', 'POST'])
@login_required(role='patient')
def home():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute("SELECT allow_register, current_number FROM system_status WHERE id=1")
    allow_register, current_number = c.fetchone()

    if request.method == 'POST' and allow_register == 1:
        if 'cancel_id' in request.form:
            cancel_id = request.form['cancel_id']
            c.execute("DELETE FROM appointments WHERE id=? AND user_id=? AND status='waiting'",
                      (cancel_id, session['user_id']))
            flash("🗑️ 已取消掛號")
        else:
            department = request.form['department']
            symptoms = request.form['symptoms']
            c.execute("INSERT INTO appointments (user_id, department, symptoms, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (session['user_id'], department, symptoms, 'waiting', datetime.now()))
            flash("✅ 掛號成功！請耐心等候")
        conn.commit()

    c.execute("SELECT department, symptoms, status, timestamp, id FROM appointments WHERE user_id=? ORDER BY id DESC",
              (session['user_id'],))
    history = c.fetchall()
    conn.close()
    return render_template('patient_home.html', allow_register=allow_register, history=history, current_number=current_number)

# 醫生頁面
@app.route('/doctor', methods=['GET', 'POST'])
@login_required(role='doctor')
def doctor():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()

    if request.method == 'POST':
        if 'stop' in request.form:
            c.execute("UPDATE system_status SET allow_register=0 WHERE id=1")
            flash("⛔ 掛號已暫停")
        elif 'resume' in request.form:
            c.execute("UPDATE system_status SET allow_register=1 WHERE id=1")
            flash("✅ 掛號已開放")
        elif 'next' in request.form:
            c.execute("SELECT id FROM appointments WHERE status='waiting' ORDER BY id ASC LIMIT 1")
            next_patient = c.fetchone()
            if next_patient:
                c.execute("UPDATE appointments SET status='called' WHERE id=?", (next_patient[0],))
                c.execute("UPDATE system_status SET current_number = current_number + 1 WHERE id=1")
                flash("🎯 已叫下一位")
        conn.commit()

    c.execute('''SELECT a.id, u.username, a.department, a.symptoms
                 FROM appointments a JOIN users u ON a.user_id = u.id
                 WHERE a.status = 'waiting'
                 ORDER BY a.id ASC''')
    waiting_list = c.fetchall()
    c.execute("SELECT current_number FROM system_status WHERE id=1")
    current_number = c.fetchone()[0]
    conn.close()
    return render_template('doctor_home.html', waiting=waiting_list, current_number=current_number)

# 管理頁：審核醫師帳號
@app.route('/admin')
@login_required(role='doctor')
def admin():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE role='doctor' AND approved=0")
    pending = c.fetchall()
    output = "<h1>等待審核醫生帳號</h1>"
    for p in pending:
        output += f"<p>{p[1]} - <a href='/approve/{p[0]}'>通過</a></p>"
    return output

@app.route('/approve/<int:doctor_id>')
@login_required(role='doctor')
def approve(doctor_id):
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved=1 WHERE id=?", (doctor_id,))
    conn.commit()
    conn.close()
    flash("✅ 已通過醫生帳號審核")
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
