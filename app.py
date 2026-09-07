from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import or_, text

from datetime import datetime
from io import BytesIO
import re
import os

app = Flask(__name__)

app.secret_key = "voice-vault-ai-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///voice_vault.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODELS
# =========================================================

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )


class VoiceNote(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        default="General"
    )

    priority = db.Column(
        db.String(50),
        default="Normal"
    )

    summary = db.Column(
        db.Text,
        default=""
    )

    keywords = db.Column(
        db.Text,
        default=""
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Task(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    task = db.Column(
        db.String(300),
        nullable=False
    )

    due_date = db.Column(
        db.String(20)
    )

    due_time = db.Column(
        db.String(20)
    )

    priority = db.Column(
        db.String(20),
        default="Medium"
    )

    status = db.Column(
        db.String(20),
        default="Pending"
    )

    reminder = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# DATABASE MIGRATION
# =========================================================

def migrate_database():

    """
    Existing VoiceNote table ki new columns missing unte
    automatically add chestundi.
    """

    try:

        inspector_query = db.session.execute(
            text("PRAGMA table_info(voice_note)")
        )

        columns = [
            row[1]
            for row in inspector_query.fetchall()
        ]

        if "summary" not in columns:

            db.session.execute(
                text(
                    "ALTER TABLE voice_note "
                    "ADD COLUMN summary TEXT DEFAULT ''"
                )
            )

        if "keywords" not in columns:

            db.session.execute(
                text(
                    "ALTER TABLE voice_note "
                    "ADD COLUMN keywords TEXT DEFAULT ''"
                )
            )

        if "created_at" not in columns:

            db.session.execute(
                text(
                    "ALTER TABLE voice_note "
                    "ADD COLUMN created_at DATETIME"
                )
            )

        db.session.commit()

    except Exception as error:

        db.session.rollback()
        print("Migration:", error)


# =========================================================
# AI HELPER FUNCTIONS
# =========================================================

def generate_summary(content):

    """
    Basic local AI-style summarization.
    No API key required.
    """

    content = content.strip()

    if not content:
        return ""

    sentences = re.split(
        r"(?<=[.!?])\s+",
        content
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    if len(sentences) <= 2:

        return content

    return " ".join(sentences[:2])


def detect_category(content):

    text_content = content.lower()

    categories = {

        "Study": [
            "study",
            "exam",
            "assignment",
            "project",
            "class",
            "college",
            "machine learning",
            "python",
            "database",
            "subject",
            "homework",
            "lab"
        ],

        "Meeting": [
            "meeting",
            "discuss",
            "discussion",
            "team",
            "manager",
            "agenda",
            "conference"
        ],

        "Work": [
            "work",
            "office",
            "client",
            "report",
            "deadline",
            "employee",
            "company"
        ],

        "Personal": [
            "home",
            "family",
            "shopping",
            "personal",
            "birthday",
            "doctor",
            "buy",
            "visit"
        ]
    }

    scores = {}

    for category, words in categories.items():

        score = 0

        for word in words:

            if word in text_content:
                score += 1

        scores[category] = score

    best_category = max(
        scores,
        key=scores.get
    )

    if scores[best_category] == 0:

        return "General"

    return best_category


def detect_priority(content):

    text_content = content.lower()

    high_words = [
        "urgent",
        "important",
        "asap",
        "immediately",
        "deadline",
        "today",
        "submit",
        "emergency",
        "critical"
    ]

    medium_words = [
        "tomorrow",
        "soon",
        "meeting",
        "assignment",
        "project"
    ]

    for word in high_words:

        if word in text_content:
            return "High"

    for word in medium_words:

        if word in text_content:
            return "Medium"

    return "Low"


def extract_keywords(content):

    stop_words = {
        "the",
        "is",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "this",
        "that",
        "are",
        "was",
        "be",
        "i",
        "we",
        "you",
        "my",
        "it"
    }

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9+#.-]{2,}",
        content
    )

    frequency = {}

    for word in words:

        word = word.lower()

        if word in stop_words:
            continue

        frequency[word] = frequency.get(
            word,
            0
        ) + 1

    sorted_words = sorted(
        frequency,
        key=frequency.get,
        reverse=True
    )

    return ", ".join(
        sorted_words[:8]
    )


def extract_tasks(content):

    """
    Basic task extraction.
    Detects sentences containing task/action words.
    """

    task_words = [
        "submit",
        "prepare",
        "complete",
        "finish",
        "attend",
        "call",
        "send",
        "buy",
        "study",
        "meet",
        "discuss",
        "create",
        "upload",
        "download",
        "do"
    ]

    sentences = re.split(
        r"(?<=[.!?])\s+",
        content
    )

    tasks = []

    for sentence in sentences:

        sentence_lower = sentence.lower()

        for word in task_words:

            if word in sentence_lower:

                tasks.append(
                    sentence.strip()
                )

                break

    return tasks


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get(
            "confirm_password"
        )

        if not name or not email or not password:

            flash(
                "Please fill all the fields."
            )

            return redirect(
                url_for("register")
            )

        if password != confirm_password:

            flash(
                "Passwords do not match."
            )

            return redirect(
                url_for("register")
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already registered."
            )

            return redirect(
                url_for("register")
            )

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)

        db.session.commit()

        flash(
            "Registration successful! Please login."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            session["user_id"] = user.id

            session["user_name"] = user.name

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    notes = VoiceNote.query.filter_by(
        user_id=user_id
    ).all()

    tasks = Task.query.filter_by(
        user_id=user_id
    ).all()

    total_notes = len(notes)

    total_tasks = len(tasks)

    completed_tasks = len([
        task
        for task in tasks
        if task.status == "Completed"
    ])

    pending_tasks = total_tasks - completed_tasks

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        total_notes=total_notes,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks
    )


# =========================================================
# RECORD
# =========================================================

@app.route("/record")
def record():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "record.html"
    )


# =========================================================
# SAVE NOTE
# =========================================================

@app.route(
    "/save_note",
    methods=["POST"]
)
def save_note():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    title = request.form.get("title")
    content = request.form.get("content")

    if not content:

        flash(
            "Please enter or record some content."
        )

        return redirect(
            url_for("record")
        )

    if not title:

        title = "Voice Note"

    summary = generate_summary(
        content
    )

    category = detect_category(
        content
    )

    priority = detect_priority(
        content
    )

    keywords = extract_keywords(
        content
    )

    new_note = VoiceNote(

        user_id=session["user_id"],

        title=title,

        content=content,

        category=category,

        priority=priority,

        summary=summary,

        keywords=keywords,

        created_at=datetime.utcnow()
    )

    db.session.add(new_note)

    # Automatically extract tasks
    detected_tasks = extract_tasks(
        content
    )

    for task_text in detected_tasks:

        new_task = Task(

            user_id=session["user_id"],

            task=task_text,

            due_date="",

            due_time="",

            priority=priority,

            status="Pending",

            reminder=False
        )

        db.session.add(new_task)

    db.session.commit()

    flash(
        "Voice note analyzed and saved successfully!"
    )

    return redirect(
        url_for("notes")
    )


# =========================================================
# NOTES
# =========================================================

@app.route("/notes")
def notes():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_notes = VoiceNote.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        VoiceNote.id.desc()
    ).all()

    return render_template(
        "notes.html",
        notes=user_notes
    )


# =========================================================
# VIEW NOTE
# =========================================================

@app.route(
    "/note/<int:note_id>"
)
def view_note(note_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    note = VoiceNote.query.filter_by(
        id=note_id,
        user_id=session["user_id"]
    ).first_or_404()

    return render_template(
        "view_note.html",
        note=note
    )


# =========================================================
# DELETE NOTE
# =========================================================

@app.route(
    "/delete_note/<int:note_id>"
)
def delete_note(note_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    note = VoiceNote.query.filter_by(
        id=note_id,
        user_id=session["user_id"]
    ).first_or_404()

    db.session.delete(note)

    db.session.commit()

    flash(
        "Voice note deleted successfully."
    )

    return redirect(
        url_for("notes")
    )


# =========================================================
# SEARCH
# =========================================================

@app.route(
    "/search",
    methods=["GET", "POST"]
)
def search():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    results = []

    search_query = ""

    if request.method == "POST":

        search_query = request.form.get(
            "query",
            ""
        ).strip()

        if search_query:

            search_pattern = (
                "%" +
                search_query +
                "%"
            )

            results = VoiceNote.query.filter(

                VoiceNote.user_id ==
                session["user_id"],

                or_(

                    VoiceNote.title.ilike(
                        search_pattern
                    ),

                    VoiceNote.content.ilike(
                        search_pattern
                    ),

                    VoiceNote.category.ilike(
                        search_pattern
                    ),

                    VoiceNote.keywords.ilike(
                        search_pattern
                    ),

                    VoiceNote.summary.ilike(
                        search_pattern
                    )
                )

            ).order_by(
                VoiceNote.id.desc()
            ).all()

    return render_template(
        "search.html",
        results=results,
        search_query=search_query
    )


# =========================================================
# TASKS
# =========================================================

@app.route("/tasks")
def tasks():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_tasks = Task.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        Task.status.asc(),
        Task.due_date.asc(),
        Task.due_time.asc()
    ).all()

    return render_template(
        "tasks.html",
        tasks=user_tasks
    )


# =========================================================
# ADD TASK
# =========================================================

@app.route(
    "/add_task",
    methods=["POST"]
)
def add_task():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    task_name = request.form.get(
        "task"
    )

    due_date = request.form.get(
        "due_date"
    )

    due_time = request.form.get(
        "due_time"
    )

    priority = request.form.get(
        "priority",
        "Medium"
    )

    reminder = request.form.get(
        "reminder"
    )

    if not task_name:

        flash(
            "Please enter a task."
        )

        return redirect(
            url_for("tasks")
        )

    new_task = Task(

        user_id=session["user_id"],

        task=task_name,

        due_date=due_date,

        due_time=due_time,

        priority=priority,

        status="Pending",

        reminder=True
        if reminder
        else False
    )

    db.session.add(new_task)

    db.session.commit()

    flash(
        "Task added successfully!"
    )

    return redirect(
        url_for("tasks")
    )


# =========================================================
# EDIT TASK
# =========================================================

@app.route(
    "/edit_task/<int:task_id>",
    methods=["GET", "POST"]
)
def edit_task(task_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    task = Task.query.filter_by(
        id=task_id,
        user_id=session["user_id"]
    ).first_or_404()

    if request.method == "POST":

        task.task = request.form.get(
            "task"
        )

        task.due_date = request.form.get(
            "due_date"
        )

        task.due_time = request.form.get(
            "due_time"
        )

        task.priority = request.form.get(
            "priority"
        )

        task.reminder = (
            True
            if request.form.get("reminder")
            else False
        )

        db.session.commit()

        flash(
            "Task updated successfully!"
        )

        return redirect(
            url_for("tasks")
        )

    return render_template(
        "edit_task.html",
        task=task
    )


# =========================================================
# COMPLETE TASK
# =========================================================

@app.route(
    "/complete_task/<int:task_id>"
)
def complete_task(task_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    task = Task.query.filter_by(
        id=task_id,
        user_id=session["user_id"]
    ).first_or_404()

    task.status = "Completed"

    db.session.commit()

    flash(
        "Task completed!"
    )

    return redirect(
        url_for("tasks")
    )


# =========================================================
# DELETE TASK
# =========================================================

@app.route(
    "/delete_task/<int:task_id>"
)
def delete_task(task_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    task = Task.query.filter_by(
        id=task_id,
        user_id=session["user_id"]
    ).first_or_404()

    db.session.delete(task)

    db.session.commit()

    flash(
        "Task deleted!"
    )

    return redirect(
        url_for("tasks")
    )


# =========================================================
# STATISTICS
# =========================================================

@app.route("/statistics")
def statistics():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    notes = VoiceNote.query.filter_by(
        user_id=user_id
    ).all()

    tasks = Task.query.filter_by(
        user_id=user_id
    ).all()

    category_counts = {}

    for note in notes:

        category = note.category or "General"

        category_counts[category] = (
            category_counts.get(
                category,
                0
            ) + 1
        )

    priority_counts = {}

    for task in tasks:

        priority = task.priority or "Medium"

        priority_counts[priority] = (
            priority_counts.get(
                priority,
                0
            ) + 1
        )

    completed = len([
        task
        for task in tasks
        if task.status == "Completed"
    ])

    pending = len(tasks) - completed

    return render_template(
        "statistics.html",

        total_notes=len(notes),

        total_tasks=len(tasks),

        completed=completed,

        pending=pending,

        category_counts=category_counts,

        priority_counts=priority_counts
    )


# =========================================================
# AI CHAT
# =========================================================

@app.route(
    "/chat",
    methods=["GET", "POST"]
)
def chat():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    answer = None

    question = ""

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        if question:

            words = [
                word.lower()
                for word in re.findall(
                    r"[A-Za-z]+",
                    question
                )
            ]

            user_notes = VoiceNote.query.filter_by(
                user_id=session["user_id"]
            ).all()

            matched_notes = []

            for note in user_notes:

                note_text = (
                    note.title +
                    " " +
                    note.content +
                    " " +
                    (note.keywords or "")
                ).lower()

                score = sum(
                    1
                    for word in words
                    if len(word) > 2
                    and word in note_text
                )

                if score > 0:

                    matched_notes.append(
                        (score, note)
                    )

            matched_notes.sort(
                key=lambda x: x[0],
                reverse=True
            )

            if matched_notes:

                answer_parts = []

                for _, note in matched_notes[:3]:

                    answer_parts.append(
                        f"📌 {note.title}: "
                        f"{note.summary or note.content}"
                    )

                answer = "\n\n".join(
                    answer_parts
                )

            else:

                answer = (
                    "I could not find a matching "
                    "voice note in your vault."
                )

    return render_template(
        "chat.html",
        question=question,
        answer=answer
    )


# =========================================================
# EXPORT TXT
# =========================================================

@app.route(
    "/export_txt/<int:note_id>"
)
def export_txt(note_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    note = VoiceNote.query.filter_by(
        id=note_id,
        user_id=session["user_id"]
    ).first_or_404()

    content = f"""
VOICE VAULT AI
==============================

Title:
{note.title}

Category:
{note.category}

Priority:
{note.priority}

Summary:
{note.summary}

Keywords:
{note.keywords}

Content:
{note.content}

Created:
{note.created_at}

==============================
"""

    file_data = BytesIO(
        content.encode("utf-8")
    )

    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name="voice_note.txt",
        mimetype="text/plain"
    )


# =========================================================
# EXPORT PDF
# =========================================================

@app.route(
    "/export_pdf/<int:note_id>"
)
def export_pdf(note_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    note = VoiceNote.query.filter_by(
        id=note_id,
        user_id=session["user_id"]
    ).first_or_404()

    try:

        from reportlab.pdfgen import canvas

        buffer = BytesIO()

        pdf = canvas.Canvas(
            buffer
        )

        pdf.setTitle(
            "Voice Vault AI Note"
        )

        y = 800

        pdf.setFont(
            "Helvetica-Bold",
            20
        )

        pdf.drawString(
            50,
            y,
            "VOICE VAULT AI"
        )

        y -= 40

        pdf.setFont(
            "Helvetica",
            12
        )

        data = [

            f"Title: {note.title}",

            f"Category: {note.category}",

            f"Priority: {note.priority}",

            f"Summary: {note.summary}",

            f"Keywords: {note.keywords}",

            "",
            "Content:",
            note.content
        ]

        for line in data:

            words = line.split()

            current_line = ""

            for word in words:

                if len(
                    current_line + " " + word
                ) > 90:

                    pdf.drawString(
                        50,
                        y,
                        current_line
                    )

                    y -= 18

                    current_line = word

                else:

                    current_line += (
                        " " + word
                    )

            if current_line:

                pdf.drawString(
                    50,
                    y,
                    current_line.strip()
                )

                y -= 18

            if y < 50:

                pdf.showPage()

                y = 800

                pdf.setFont(
                    "Helvetica",
                    12
                )

        pdf.save()

        buffer.seek(0)

        return send_file(

            buffer,

            as_attachment=True,

            download_name="voice_note.pdf",

            mimetype="application/pdf"
        )

    except ImportError:

        flash(
            "Install reportlab using pip install reportlab"
        )

        return redirect(
            url_for(
                "view_note",
                note_id=note.id
            )
        )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out."
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# DATABASE
# =========================================================

with app.app_context():

    db.create_all()

    migrate_database()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )