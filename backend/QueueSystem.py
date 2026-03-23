from datetime import datetime, timedelta
from twilio.rest import Client
from dotenv import load_dotenv
import os
import joblib
import pandas as pd
import random

load_dotenv()


class QueueSystem:
    def __init__(self, start_time="10:00"):
        self.queue = []
        self.current_token = 1
        self.start_time = datetime.strptime(start_time, "%H:%M")
        self.current_patient = None
        self.consult_start_time = None

        # Twilio setup
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_number = os.getenv("twilio_number")
        self.client = Client(self.twilio_sid, self.twilio_auth)

        # Load ML model & encoders
        self.model = joblib.load("backend/models/consultation_model.pkl")
        self.le_disease = joblib.load("backend/models/le_disease.pkl")
        self.le_severity = joblib.load("backend/models/le_severity.pkl")
        self.le_visit = joblib.load("backend/models/le_visit.pkl")

    # Safe encoding for unknown categories
    def safe_transform(self, le, value):
        if value in le.classes_:
            return le.transform([value])[0]
        return -1

    # Predict consultation time
    def predict_time(self, age, disease, severity, new_or_followup, symptoms_count):
        sample = pd.DataFrame([{
            "Age": age,
            "Disease_Type": self.safe_transform(self.le_disease, disease),
            "Severity": self.safe_transform(self.le_severity, severity),
            "New_or_Followup": self.safe_transform(self.le_visit, new_or_followup),
            "Symptoms_Count": symptoms_count
        }])
        predicted = self.model.predict(sample)[0]
        # Add small random variation
        return round(predicted + random.uniform(-2, 2), 1)

    # Add patient using ML-predicted time
    def add_patient(self, name, age, disease, severity, new_or_followup, symptoms_count, phone=None):
        predicted_time = self.predict_time(age, disease, severity, new_or_followup, symptoms_count)
        start = self.start_time if not self.queue else self.queue[-1]["end_time"]
        end = start + timedelta(minutes=predicted_time)

        patient = {
            "token": self.current_token,
            "name": name,
            "predicted_time": predicted_time,
            "start_time": start,
            "end_time": end,
            "status": "WAITING",
            "phone": phone
        }

        self.queue.append(patient)
        self.current_token += 1

        if phone:
            message = self.generate_sms(patient)
            self.send_sms(phone, message)

        return patient

    # Generate QR link for SMS (public URL)
    def generate_qr_url(self, patient):
        data = f"token:{patient['token']}|name:{patient['name']}|time:{patient['start_time'].strftime('%H:%M')}"
        return f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={data}"

    # Generate SMS text including QR link
    def generate_sms(self, patient):
        qr_link = self.generate_qr_url(patient)
        return (
            f"Token: {patient['token']}\n"
            f"Name: {patient['name']}\n"
            f"Time: {patient['start_time'].strftime('%H:%M')}\n"
            f"Status: {patient['status']}\n"
            f"Scan QR: {qr_link}"
        )

    # Send SMS via Twilio
    def send_sms(self, to_number, message):
        try:
            sms = self.client.messages.create(
                body=message,
                from_=self.twilio_number,
                to=to_number
            )
            print(f"SMS sent to {to_number}: SID {sms.sid}")
        except Exception as e:
            print(f"Failed to send SMS to {to_number}: {e}")

    def check_in(self, token):
        for p in self.queue:
            if p["token"] == token:
                p["status"] = "PRESENT"
                return f"{p['name']} checked in"
        return "Invalid token"

    def get_next_patient(self):
        for p in list(self.queue):
            if p["status"] == "PRESENT":
                p["status"] = "IN_CONSULT"
                return p
            elif p["status"] == "WAITING":
                p["status"] = "SKIPPED"
                self.move_to_end(p)
        return None

    def move_to_end(self, patient):
        self.queue.remove(patient)
        patient["status"] = "WAITING"
        self.queue.append(patient)

    def start_consultation(self):
        patient = self.get_next_patient()
        if patient:
            self.current_patient = patient
            self.consult_start_time = datetime.now()
            return patient
        return None

    def end_consultation(self):
        if not self.current_patient:
            return "No active consultation"
        actual_time = (datetime.now() - self.consult_start_time).seconds / 60
        predicted_time = self.current_patient["predicted_time"]
        delay = max(actual_time - predicted_time, -5)
        self.current_patient["status"] = "DONE"
        self.shift_queue_dynamic(delay)
        finished_patient = self.current_patient["name"]
        self.current_patient = None
        self.consult_start_time = None
        return f"{finished_patient} done. Delay: {round(delay,1)} min"

    def shift_queue_dynamic(self, delay):
        for p in self.queue:
            if p["status"] in ["WAITING", "PRESENT"]:
                p["start_time"] += timedelta(minutes=delay)
                p["end_time"] += timedelta(minutes=delay)

    def add_break(self, break_time, duration):
        break_start = datetime.strptime(break_time, "%H:%M")
        for p in self.queue:
            if p["start_time"] >= break_start:
                p["start_time"] += timedelta(minutes=duration)
                p["end_time"] += timedelta(minutes=duration)
            elif p["start_time"] < break_start and p["end_time"] > break_start:
                p["end_time"] += timedelta(minutes=duration)
                self.shift_queue_dynamic(duration)

    def show_queue(self):
        print("\n--- Queue Status ---")
        for p in self.queue:
            print(
                f"Token {p['token']} | {p['name']} | "
                f"{p['start_time'].strftime('%H:%M')} - {p['end_time'].strftime('%H:%M')} | "
                f"{p['status']}"
            )


# --- Example usage ---
if __name__ == "__main__":
    qs = QueueSystem("10:00")

    p1 = qs.add_patient(
        name="Alice",
        age=25,
        disease="Fever",
        severity="Medium",
        new_or_followup="New",
        symptoms_count=4,
        phone="+919921616017"
    )
    p2 = qs.add_patient(
        name="Bob",
        age=40,
        disease="Diabetes",
        severity="High",
        new_or_followup="Followup",
        symptoms_count=3,
        phone="+917558214666"
    )
    p3 = qs.add_patient(
        name="Charlie",
        age=30,
        disease="Cold",
        severity="Low",
        new_or_followup="New",
        symptoms_count=2
    )  # no phone, no SMS

    qs.show_queue()