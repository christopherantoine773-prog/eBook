import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, flash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "booksite.db"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "epub"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

BOOK = {
    "title": os.environ.get("BOOK_TITLE", "The Echo of a Silence"),
    "author": os.environ.get("BOOK_AUTHOR", "Antoine Christopher"),
    "description": os.environ.get(
        "BOOK_DESCRIPTION",
        "Un livre intime sur les silences, les pensées et les choses que l’on garde parfois en soi."
    ),
    "cover": "cover-placeholder.svg",
}

def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_files (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
        """)
        # Initial display counts: these are starting values, not fabricated ongoing traffic.
        defaults = {"views": 800, "downloads": 264, "readers": 137, "shares": 42}
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO stats(key, value) VALUES(?, ?)", (key, value))
        conn.commit()

def get_stat(key):
    with db() as conn:
        row = conn.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
        return int(row["value"]) if row else 0

def increment_stat(key):
    with db() as conn:
        conn.execute("UPDATE stats SET value = value + 1 WHERE key = ?", (key,))
        conn.execute("INSERT INTO events(kind, created_at) VALUES(?, ?)",
                     (key, datetime.utcnow().isoformat(timespec="seconds")))
        conn.commit()

def get_chart_data():
    # Shows the last 7 days. Initial baseline is visible on the main counters;
    # daily chart values are real events recorded by this site.
    labels, views, downloads = [], [], []
    today = datetime.utcnow().date()
    with db() as conn:
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            labels.append(day.strftime("%d %b"))
            start = datetime.combine(day, datetime.min.time()).isoformat()
            end = datetime.combine(day + timedelta(days=1), datetime.min.time()).isoformat()
            v = conn.execute("SELECT COUNT(*) n FROM events WHERE kind='views' AND created_at >= ? AND created_at < ?", (start, end)).fetchone()["n"]
            d = conn.execute("SELECT COUNT(*) n FROM events WHERE kind='downloads' AND created_at >= ? AND created_at < ?", (start, end)).fetchone()["n"]
            views.append(v)
            downloads.append(d)
    return labels, views, downloads

def get_book_file():
    with db() as conn:
        return conn.execute("SELECT * FROM book_files WHERE id=1").fetchone()

@app.route("/")
def index():
    increment_stat("views")
    labels, chart_views, chart_downloads = get_chart_data()
    book_file = get_book_file()
    stats = {
        "views": get_stat("views"),
        "downloads": get_stat("downloads"),
        "readers": get_stat("readers"),
        "shares": get_stat("shares"),
    }
    return render_template(
        "index.html", book=BOOK, stats=stats, book_file=book_file,
        labels=labels, chart_views=chart_views, chart_downloads=chart_downloads
    )

@app.route("/read")
def read_book():
    book_file = get_book_file()
    if not book_file:
        flash("Le livre n’a pas encore été ajouté. Revenez bientôt.", "info")
        return redirect(url_for("index"))
    if not book_file["original_name"].lower().endswith(".pdf"):
        flash("La lecture intégrée est disponible pour les fichiers PDF. Téléchargez l’EPUB pour le lire dans votre application préférée.", "info")
        return redirect(url_for("index"))
    increment_stat("readers")
    return render_template("reader.html", book=BOOK, filename=book_file["filename"])

@app.route("/download")
def download_book():
    book_file = get_book_file()
    if not book_file:
        flash("Le livre n’est pas encore disponible au téléchargement.", "info")
        return redirect(url_for("index"))
    increment_stat("downloads")
    return send_from_directory(UPLOAD_DIR, book_file["filename"], as_attachment=True,
                               download_name=book_file["original_name"])

@app.route("/book-file/<path:filename>")
def serve_book_file(filename):
    # Used only by the embedded PDF reader; file names are generated by the server.
    book_file = get_book_file()
    if not book_file or filename != book_file["filename"]:
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    # Minimal password gate. Set ADMIN_PASSWORD in Render environment variables.
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        return ("Configurez la variable ADMIN_PASSWORD dans Render avant d’utiliser cette page.", 503)
    if request.method == "POST":
        if request.form.get("password") != password:
            flash("Mot de passe incorrect.", "error")
            return render_template("admin.html")
        # Successful login is intentionally one-request only for this simple starter.
        # Keep the upload endpoint behind the same password check below.
        return render_template("admin.html", authorized=True)
    return render_template("admin.html", authorized=False)

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    password = os.environ.get("ADMIN_PASSWORD")
    if not password or request.form.get("password") != password:
        abort(403)
    file = request.files.get("book_file")
    if not file or not file.filename:
        flash("Choisissez un fichier PDF ou EPUB.", "error")
        return redirect(url_for("admin"))
    original = secure_filename(file.filename)
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash("Format non accepté. Utilisez PDF ou EPUB.", "error")
        return redirect(url_for("admin"))
    stored_name = f"book_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{extension}"
    file.save(UPLOAD_DIR / stored_name)
    with db() as conn:
        conn.execute("""
            INSERT INTO book_files(id, filename, original_name, uploaded_at)
            VALUES(1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET filename=excluded.filename,
                original_name=excluded.original_name, uploaded_at=excluded.uploaded_at
        """, (stored_name, original, datetime.utcnow().isoformat(timespec="seconds")))
        conn.commit()
    flash("Le livre a été publié avec succès.", "success")
    return redirect(url_for("admin"))

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
