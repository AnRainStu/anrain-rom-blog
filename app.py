import functools
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('ANRAIN_DATA_DIR', BASE / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
key_path = DATA / 'secret.key'
if not key_path.exists():
    try:
        with key_path.open('x', encoding='utf-8') as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or key_path.read_text(encoding='utf-8').strip(),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1', MAX_CONTENT_LENGTH=1024 * 1024)

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATA / 'blog.sqlite3')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error):
    if 'db' in g:
        g.db.close()

def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS posts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
      version TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL, body TEXT NOT NULL,
      download_url TEXT NOT NULL DEFAULT '', extra_url TEXT NOT NULL DEFAULT '',
      published_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      show_donation INTEGER NOT NULL DEFAULT 0, extra_label TEXT NOT NULL DEFAULT ''
    );''')
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(posts)')}
    if 'extra_label' not in columns:
        conn.execute("ALTER TABLE posts ADD COLUMN extra_label TEXT NOT NULL DEFAULT ''")
    if not conn.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
        from seed import POSTS
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.executemany('INSERT INTO posts (title,category,version,summary,body,download_url,extra_url,published_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                         [(*p, now, now) for p in POSTS])
        conn.execute("UPDATE posts SET show_donation=1 WHERE title LIKE '%Android 17%'")
        conn.execute("INSERT INTO settings VALUES ('seeded','1')")
    conn.execute("UPDATE posts SET extra_label='设备树' WHERE extra_label='' AND extra_url LIKE '%android_device_oneplus_pagani%'")
    conn.execute("UPDATE posts SET extra_label='C.701 底包' WHERE extra_label='' AND extra_url LIKE '%1BaUVv-u7Xdd%'")
    conn.commit()

@app.cli.command('set-admin')
def set_admin():
    """Set or reset the administrator password interactively."""
    password = click.prompt('管理员密码（至少 12 个字符）', hide_input=True, confirmation_prompt=True)
    if len(password) < 12:
        raise click.ClickException('密码至少需要 12 个字符')
    conn = db()
    conn.execute("INSERT INTO settings(key,value) VALUES('password',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (generate_password_hash(password),))
    conn.commit()
    click.echo('管理员密码已设置。')

def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def protect_post():
    if request.method == 'POST' and not secrets.compare_digest(session.get('csrf', ''), request.form.get('csrf_token', '') or 'invalid'):
        abort(400, '表单已过期，请刷新页面后重试。')

def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

def get_post(post_id):
    post = db().execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
    if post is None:
        abort(404)
    return post

@app.route('/')
def index():
    q = request.args.get('q', '').strip()[:100]
    category = request.args.get('category', '').strip()[:100]
    groups = {'native': ('类原生', ('Android 16', 'Android 17', '类原生')),
              'official': ('官改', ('官改 ROM', '官改')),
              'port': ('移植', ('移植 ROM', '应用移植', '移植'))}
    if category not in groups:
        row = db().execute("SELECT value FROM settings WHERE key='work_status'").fetchone()
        return render_template('choose.html', work_status=(row['value'] if row and row['value'] else '暂未设置工作状态'), device=request.args.get('device') == 'oneplus-13t')
    group_name, group_categories = groups[category]
    sql, args = 'SELECT * FROM posts WHERE 1=1', []
    if q:
        sql += ' AND (title LIKE ? OR summary LIKE ? OR body LIKE ? OR version LIKE ?)'
        args += ['%' + q + '%'] * 4
    sql += ' AND category IN (' + ','.join('?' for _ in group_categories) + ')'
    args.extend(group_categories)
    posts = db().execute(sql + ' ORDER BY published_at DESC, id DESC', args).fetchall()
    return render_template('index.html', posts=posts, group_name=group_name, q=q, category=category)

@app.route('/post/<int:post_id>')
def post(post_id):
    return render_template('post.html', post=get_post(post_id))

@app.route('/AnPHadmin/login', methods=['GET', 'POST'])
def login():
    configured = db().execute("SELECT value FROM settings WHERE key='password'").fetchone()
    if request.method == 'POST':
        if configured and check_password_hash(configured['value'], request.form.get('password', '')):
            session.clear()
            session['admin'] = True
            return redirect(url_for('admin'))
        flash('密码不正确，或尚未设置管理员密码。', 'error')
    return render_template('login.html', configured=bool(configured))

@app.route('/AnPHadmin/logout', methods=['POST'])
@admin_required
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/AnPHadmin')
@admin_required
def admin():
    posts = db().execute('SELECT * FROM posts ORDER BY published_at DESC, id DESC').fetchall()
    row = db().execute("SELECT value FROM settings WHERE key='work_status'").fetchone()
    return render_template('admin.html', posts=posts, work_status=row['value'] if row else '')

@app.route('/AnPHadmin/status', methods=['POST'])
@admin_required
def update_status():
    status = request.form.get('work_status', '').strip()
    if len(status) > 120:
        flash('工作状态不能超过 120 个字符。', 'error')
    else:
        db().execute("INSERT INTO settings(key,value) VALUES('work_status',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (status,))
        db().commit()
        flash('工作状态已更新。', 'success')
    return redirect(url_for('admin'))

@app.route('/AnPHadmin/new', methods=['GET', 'POST'])
@app.route('/AnPHadmin/edit/<int:post_id>', methods=['GET', 'POST'])
@admin_required
def edit(post_id=None):
    post = get_post(post_id) if post_id else None
    if request.method == 'POST':
        data = {k: request.form.get(k, '').strip() for k in ('title','category','version','summary','body','download_url','extra_url','extra_label','published_at')}
        error = None
        if not all(data[k] for k in ('title','category','summary','body','published_at')):
            error = '请填写标题、分类、摘要、正文和发布日期。'
        elif data['category'] not in ('Android 16', 'Android 17', '类原生', '官改 ROM', '官改', '移植 ROM', '应用移植', '移植'):
            error = '请选择有效的文章分类。'
        elif any(len(data[k]) > limit for k, limit in [('title',200),('category',60),('version',100),('summary',500),('body',30000),('download_url',2000),('extra_url',2000),('extra_label',60)]):
            error = '字段内容过长，请缩短后重试。'
        else:
            try:
                datetime.strptime(data['published_at'], '%Y-%m-%d')
            except ValueError:
                error = '发布日期格式应为 YYYY-MM-DD。'
            for key in ('download_url', 'extra_url'):
                if data[key]:
                    parsed = urlparse(data[key])
                    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                        error = '链接必须是完整的 http 或 https 地址。'
        if error:
            flash(error, 'error')
            data['show_donation'] = request.form.get('show_donation') == '1'
            post = data
        else:
            conn = db()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            values = tuple(data[k] for k in ('title','category','version','summary','body','download_url','extra_url','published_at'))
            if post_id:
                conn.execute('UPDATE posts SET title=?,category=?,version=?,summary=?,body=?,download_url=?,extra_url=?,published_at=?,updated_at=?,show_donation=?,extra_label=? WHERE id=?', (*values, now, int(request.form.get('show_donation') == '1'), data['extra_label'], post_id))
            else:
                conn.execute('INSERT INTO posts(title,category,version,summary,body,download_url,extra_url,published_at,created_at,updated_at,show_donation,extra_label) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (*values, now, now, int(request.form.get('show_donation') == '1'), data['extra_label']))
            conn.commit()
            flash('文章已保存。', 'success')
            return redirect(url_for('admin'))
    return render_template('edit.html', post=post, is_edit=post_id is not None, today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/AnPHadmin/delete/<int:post_id>', methods=['POST'])
@admin_required
def delete(post_id):
    get_post(post_id)
    db().execute('DELETE FROM posts WHERE id=?', (post_id,))
    db().commit()
    flash('文章已删除。', 'success')
    return redirect(url_for('admin'))

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
