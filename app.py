import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, flash, session
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
RENDER_DATA_DIR = Path("/var/data")
DATA_DIR = Path(os.environ.get("DATA_DIR", str(RENDER_DATA_DIR if RENDER_DATA_DIR.exists() else BASE_DIR)))
DATABASE = Path(os.environ.get("DATABASE_PATH", str(DATA_DIR / "booksite.db")))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_FOLDER", str(DATA_DIR / "uploads")))
DATABASE.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "epub"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

DEFAULT_BOOK = {
    "title": os.environ.get("BOOK_TITLE", "The Echo of a Silence"),
    "author": os.environ.get("BOOK_AUTHOR", "Antoine Christopher"),
    "description": os.environ.get("BOOK_DESCRIPTION", "Un livre intime sur les silences, les pensées et les choses que l’on garde parfois en soi."),
    "cover": "cover-placeholder.svg",
}

def db():
    connection = sqlite3.connect(DATABASE, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS book_files (
            id INTEGER PRIMARY KEY CHECK (id = 1), filename TEXT NOT NULL,
            original_name TEXT NOT NULL, uploaded_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, author TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', cover TEXT NOT NULL DEFAULT 'cover-placeholder.svg',
            filename TEXT, original_name TEXT, uploaded_at TEXT,
            views INTEGER NOT NULL DEFAULT 0, downloads INTEGER NOT NULL DEFAULT 0,
            readers INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
        # Statistiques de départ : les compteurs existants ne sont jamais diminués.
        defaults = {"views": 940, "downloads": 400, "readers": 137, "shares": 42}
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO stats(key, value) VALUES(?, ?)", (key, value))
        # Si la base existe déjà avec des compteurs plus bas, les relever une seule
        # fois au minimum demandé. Les prochaines vues/téléchargements s'ajoutent normalement.
        conn.execute("UPDATE stats SET value=MAX(value, 940) WHERE key='views'")
        conn.execute("UPDATE stats SET value=MAX(value, 400) WHERE key='downloads'")
        # Migrate the existing single-book database without deleting the old row or file.
        if conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            old = conn.execute("SELECT * FROM book_files WHERE id=1").fetchone()
            conn.execute("""INSERT INTO books(title, author, description, cover, filename, original_name, uploaded_at, created_at)
                            VALUES(?,?,?,?,?,?,?,?)""",
                         (DEFAULT_BOOK["title"], DEFAULT_BOOK["author"], DEFAULT_BOOK["description"],
                          DEFAULT_BOOK["cover"], old["filename"] if old else None,
                          old["original_name"] if old else None, old["uploaded_at"] if old else None,
                          datetime.utcnow().isoformat(timespec="seconds")))
        conn.commit()

def get_stat(key):
    with db() as conn:
        row = conn.execute("SELECT value FROM stats WHERE key=?", (key,)).fetchone()
        return int(row["value"]) if row else 0

def increment_stat(key, book_id=None):
    with db() as conn:
        conn.execute("UPDATE stats SET value=value+1 WHERE key=?", (key,))
        conn.execute("INSERT INTO events(kind, created_at) VALUES(?,?)",
                     (key, datetime.utcnow().isoformat(timespec="seconds")))
        if book_id is not None and key in {"views", "downloads", "readers"}:
            conn.execute(f"UPDATE books SET {key}={key}+1 WHERE id=?", (book_id,))
        conn.commit()

def get_chart_data():
    labels, views, downloads = [], [], []
    today = datetime.utcnow().date()
    with db() as conn:
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            labels.append(day.strftime("%d %b"))
            start = datetime.combine(day, datetime.min.time()).isoformat()
            end = datetime.combine(day + timedelta(days=1), datetime.min.time()).isoformat()
            views.append(conn.execute("SELECT COUNT(*) n FROM events WHERE kind='views' AND created_at>=? AND created_at<?", (start,end)).fetchone()["n"])
            downloads.append(conn.execute("SELECT COUNT(*) n FROM events WHERE kind='downloads' AND created_at>=? AND created_at<?", (start,end)).fetchone()["n"])
    return labels, views, downloads

def list_books():
    with db() as conn:
        return conn.execute("SELECT * FROM books ORDER BY id ASC").fetchall()

def get_book(book_id):
    with db() as conn:
        return conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()

def get_primary_book():
    books = list_books()
    if books:
        return books[0]
    return {**DEFAULT_BOOK, "id": None, "filename": None, "original_name": None}

def admin_authorized():
    return bool(session.get("admin_authorized"))

@app.route("/")
def index():
    books = list_books()
    primary = books[0] if books else get_primary_book()
    increment_stat("views", primary["id"] if primary and primary["id"] else None)
    labels, chart_views, chart_downloads = get_chart_data()
    book_file = None
    if primary and primary.get("filename") if isinstance(primary, dict) else primary["filename"]:
        book_file = {"filename": primary["filename"], "original_name": primary["original_name"]}
    stats = {"views": get_stat("views"), "downloads": get_stat("downloads"),
             "readers": get_stat("readers"), "shares": get_stat("shares")}
    return render_template("index.html", book=primary, stats=stats, book_file=book_file,
                           books=books, labels=labels, chart_views=chart_views, chart_downloads=chart_downloads)

@app.route("/read")
def read_book():
    books = list_books()
    book = books[0] if books else None
    if not book or not book["filename"]:
        flash("Le livre n’a pas encore été ajouté. Revenez bientôt.", "info")
        return redirect(url_for("index"))
    return redirect(url_for("read_specific_book", book_id=book["id"]))

@app.route("/books/<int:book_id>/read")
def read_specific_book(book_id):
    book = get_book(book_id)
    if not book or not book["filename"]:
        abort(404)
    if not (book["original_name"] or "").lower().endswith(".pdf"):
        flash("La lecture intégrée est disponible pour les PDF. Téléchargez l’EPUB pour le lire dans votre application préférée.", "info")
        return redirect(url_for("index"))
    increment_stat("readers", book_id)
    return render_template("reader.html", book=book, filename=book["filename"])

@app.route("/download")
def download_book():
    books = list_books()
    book = books[0] if books else None
    if not book:
        flash("Le livre n’est pas encore disponible au téléchargement.", "info")
        return redirect(url_for("index"))
    return redirect(url_for("download_specific_book", book_id=book["id"]))

@app.route("/books/<int:book_id>/download")
def download_specific_book(book_id):
    book = get_book(book_id)
    if not book or not book["filename"] or not (UPLOAD_DIR / book["filename"]).is_file():
        flash("Le fichier de ce livre n’est pas disponible pour le moment.", "error")
        return redirect(url_for("index"))
    increment_stat("downloads", book_id)
    return send_from_directory(UPLOAD_DIR, book["filename"], as_attachment=True,
                               download_name=book["original_name"])

@app.route("/book-file/<path:filename>")
def serve_book_file(filename):
    with db() as conn:
        row = conn.execute("SELECT id FROM books WHERE filename=?", (filename,)).fetchone()
    if not row or not (UPLOAD_DIR / filename).is_file():
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        return ("Configurez la variable ADMIN_PASSWORD dans Render avant d’utiliser cette page.", 503)
    if request.method == "POST":
        if request.form.get("password") != password:
            flash("Mot de passe incorrect.", "error")
            return render_template("admin.html", authorized=False, books=list_books())
        session["admin_authorized"] = True
        session.permanent = True
        return redirect(url_for("admin"))
    return render_template("admin.html", authorized=admin_authorized(), books=list_books())

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_authorized", None)
    flash("Vous êtes déconnecté de l’espace auteur.", "info")
    return redirect(url_for("admin"))

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not admin_authorized():
        abort(403)
    file = request.files.get("book_file")
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    description = request.form.get("description", "").strip()
    if not file or not file.filename or not title or not author:
        flash("Ajoute un fichier, le titre du livre et le nom de l’auteur.", "error")
        return redirect(url_for("admin"))
    original = secure_filename(file.filename)
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash("Format non accepté. Utilise un fichier PDF ou EPUB.", "error")
        return redirect(url_for("admin"))
    stored_name = f"book_{uuid.uuid4().hex}.{extension}"
    file.save(UPLOAD_DIR / stored_name)
    now = datetime.utcnow().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("""INSERT INTO books(title, author, description, cover, filename, original_name, uploaded_at, created_at)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (title, author, description or "Un livre à découvrir.", "cover-placeholder.svg",
                      stored_name, original, now, now))
        conn.commit()
    flash(f"« {title} » a été ajouté à ta bibliothèque. Les autres livres sont conservés.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    if not admin_authorized():
        abort(403)
    with db() as conn:
        row = conn.execute("SELECT filename, title FROM books WHERE id=?", (book_id,)).fetchone()
        if not row:
            abort(404)
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        conn.commit()
    # Remove only the deleted book's stored file, never any other book's file.
    if row["filename"]:
        try:
            (UPLOAD_DIR / row["filename"]).unlink(missing_ok=True)
        except OSError:
            pass
    flash(f"« {row['title']} » a été supprimé.", "success")
    return redirect(url_for("admin"))

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
