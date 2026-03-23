from flask import Flask, render_template, request, redirect, url_for, session
from backend.QueueSystem import QueueSystem
from datetime import timedelta
import json
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.permanent_session_lifetime = timedelta(hours=12)

qs = QueueSystem("10:00")

DOCTOR_FILE = "doctors.json"

def load_doctors():
    if not os.path.exists(DOCTOR_FILE):
        return []
    with open(DOCTOR_FILE, "r") as f:
        return json.load(f)

def save_doctors(doctors):
    with open(DOCTOR_FILE, "w") as f:
        json.dump(doctors, f, indent=2)

# --- User page: patient adds themselves ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"]
        age = int(request.form["age"])
        disease = request.form["disease"]
        severity = request.form["severity"]
        new_or_followup = request.form["visit"]
        symptoms_count = int(request.form["symptoms_count"])
        phone = request.form.get("phone")

        qs.add_patient(name, age, disease, severity, new_or_followup, symptoms_count, phone)
        return redirect(url_for("index"))

    return render_template("index.html")


# --- Doctor signup ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        doctors = load_doctors()
        if any(d["username"] == username for d in doctors):
            return "Username already exists", 400

        doctors.append({"username": username, "password": password})
        save_doctors(doctors)
        return redirect(url_for("login"))

    return render_template("signup.html")


# --- Doctor login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        doctors = load_doctors()
        if any(d["username"] == username and d["password"] == password for d in doctors):
            session.permanent = True
            session["doctor_logged_in"] = True
            session["doctor_username"] = username
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("doctor_logged_in", None)
    session.pop("doctor_username", None)
    return redirect(url_for("login"))


# --- Doctor dashboard ---
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not session.get("doctor_logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        if "start" in request.form:
            qs.start_consultation()
        elif "end" in request.form:
            qs.end_consultation()
        elif "break" in request.form:
            break_time = request.form["break_time"]
            duration = int(request.form["duration"])
            qs.add_break(break_time, duration)
        return redirect(url_for("dashboard"))

    queue = qs.queue
    current_patient = qs.current_patient
    return render_template("dashboard.html", queue=queue, current_patient=current_patient)


if __name__ == "__main__":
    app.run(debug=True)