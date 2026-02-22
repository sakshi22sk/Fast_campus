from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Classroom(db.Model):
    __tablename__ = "classroom"

    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(50))
    block = db.Column(db.String(50))
    room_type = db.Column(db.String(30))
    capacity = db.Column(db.Integer)
    floor = db.Column(db.Integer)

class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(100))
    employee_id = db.Column(db.String(50))   # ✅ ADD THIS

    email = db.Column(db.String(100))
    department = db.Column(db.String(50))
    designation = db.Column(db.String(50))
    specialization = db.Column(db.String(100))
    max_hours = db.Column(db.Integer)

class Timetable(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    classroom_id = db.Column(db.Integer, db.ForeignKey("classroom.id"))
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"))

    students = db.Column(db.Integer)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)

    status = db.Column(db.String(20), default="ACTIVE")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classroom = db.relationship("Classroom")
    faculty = db.relationship("Faculty")
