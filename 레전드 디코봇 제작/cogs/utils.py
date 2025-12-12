import sqlite3

def connect_db():
    return sqlite3.connect('eco_rpg.db') 

def get_user_data(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data

def update_user_data(user_id, column, value):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def ensure_user_registered(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO users (user_id, money, current_job, health, hunger, credit_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, 1000, '시민', 100, 100, 50))
        conn.commit()
        print(f"새로운 유저 등록 완료: {user_id}")
        conn.close()
        return True
    
    conn.close()
    return False