from flask import Flask, render_template, request, redirect
from models import db, Classroom, Faculty, Timetable
from flask_apscheduler import APScheduler
from datetime import datetime
import csv
from flask_socketio import SocketIO
import os

app = Flask(__name__)


app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
socketio = SocketIO(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

with app.app_context():
    db.create_all()

# ---------------- LOGIN ----------------

@app.route("/", methods=["GET","POST"])
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        flash("Registration Successful!", "success")

        return redirect(url_for("register"))

    return render_template("register.html")
# ---------------- IMPORT ROOMS ----------------

@app.route("/import_rooms")
def import_rooms():

    with open("classrooms.csv") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.session.add(Classroom(
                room_name=row["room_name"],
                block=row["block"],
                room_type=row["room_type"],
                capacity=int(row["capacity"]),
                floor=int(row["floor"])
            ))

        db.session.commit()

    return "Rooms Imported"

# ---------------- CLASSROOMS ----------------

@app.route("/classrooms", methods=["GET","POST"])
def classrooms():

    if request.method == "POST":
        db.session.add(Classroom(
            room_name=request.form["room_name"],
            block=request.form["block"],
            room_type=request.form["room_type"],
            capacity=int(request.form["capacity"]),
            floor=int(request.form["floor"])
        ))
        db.session.commit()
        return redirect("/classrooms")

    return render_template("classrooms.html", rooms=Classroom.query.all())

# ---------------- FACULTY ----------------

@app.route("/faculty", methods=["GET","POST"])
def faculty():

    if request.method == "POST":
        db.session.add(Faculty(
            full_name=request.form["full_name"],
            employee_id=request.form["employee_id"],
            email=request.form["email"],
            department=request.form["department"],
            designation=request.form["designation"],
            specialization=request.form["specialization"],
            max_hours=int(request.form["max_hours"])
        ))
        db.session.commit()
        return redirect("/faculty")

    faculty = Faculty.query.all()
    schedules = Timetable.query.filter_by(status="ACTIVE").all()

    faculty_chart = []

    for f in faculty:
        total_minutes = 0

        for s in schedules:
            if s.faculty_id == f.id:
                start = datetime.combine(datetime.today(), s.start_time)
                end = datetime.combine(datetime.today(), s.end_time)
                if end > start:
                    total_minutes += (end-start).total_seconds()/60

        hours = round(total_minutes/60,1)
        load = round((hours/f.max_hours)*100) if f.max_hours else 0
        load = min(load,150)

        if load < 40:
            status="Underused"
        elif load<=100:
            status="Optimal"
        else:
            status="Overloaded"

        faculty_chart.append({
            "name":f.full_name,
            "load":load,
            "hours":hours,
            "status":status
        })

    return render_template("faculty.html",faculty=faculty,faculty_chart=faculty_chart)

# ---------------- TIMETABLE ----------------

@app.route("/timetable", methods=["GET","POST"])
def timetable():

    start_time=request.args.get("start_time")
    end_time=request.args.get("end_time")

    free_rooms=[]
    free_faculty=[]

    if start_time and end_time:

        st=datetime.strptime(start_time,"%H:%M").time()
        et=datetime.strptime(end_time,"%H:%M").time()

        free_rooms = Classroom.query.filter(
            ~Classroom.id.in_(
                db.session.query(Timetable.classroom_id).filter(
                    Timetable.status=="ACTIVE",
                    Timetable.start_time < et,
                    Timetable.end_time > st
                )
            )
        ).all()

        free_faculty = Faculty.query.filter(
            ~Faculty.id.in_(
                db.session.query(Timetable.faculty_id).filter(
                    Timetable.status=="ACTIVE",
                    Timetable.start_time < et,
                    Timetable.end_time > st
                )
            )
        ).all()

    if request.method=="POST":

        st=datetime.strptime(request.form["start_time"],"%H:%M")
        et=datetime.strptime(request.form["end_time"],"%H:%M")

        db.session.add(Timetable(
            classroom_id=int(request.form["classroom_id"]),
            faculty_id=int(request.form["faculty_id"]),
            students=int(request.form["students"]),
            start_time=st.time(),
            end_time=et.time(),
            status="ACTIVE"
        ))

        db.session.commit()
        return redirect("/timetable")

    return render_template(
        "timetable.html",
        classrooms=free_rooms,
        faculty=free_faculty,
        timetables=Timetable.query.all(),
        start_time=start_time,
        end_time=end_time
    )

# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    rooms=Classroom.query.all()
    faculty=Faculty.query.all()
    schedules=Timetable.query.filter_by(status="ACTIVE").all()

    students_today=sum(s.students for s in schedules)

    total_capacity=sum(r.capacity for r in rooms)
    total_students=sum(s.students for s in schedules)
    utilization=int((total_students/total_capacity)*100) if total_capacity else 0

    room_util=[]
    for r in rooms:
        used=sum(s.students for s in schedules if s.classroom_id==r.id)
        percent=int((used/r.capacity)*100) if r.capacity else 0
        room_util.append({
            "name":r.room_name,
            "students":used,
            "capacity":r.capacity,
            "percent":percent
        })

    faculty_load=[]
    total_faculty=0

    for f in faculty:
        mins=0
        for s in schedules:
            if s.faculty_id==f.id:
                mins+=(datetime.combine(datetime.today(),s.end_time)-datetime.combine(datetime.today(),s.start_time)).total_seconds()/60

        hours=mins/60
        load=int((hours/f.max_hours)*100) if f.max_hours else 0
        total_faculty+=load

        faculty_load.append({"name":f.full_name,"load":load})

    faculty_capacity=int(total_faculty/len(faculty)) if faculty else 0

    under_rooms=[r for r in room_util if r["percent"]<40]
    large_rooms=[r for r in room_util if r["capacity"]>=100 and r["percent"]<40]
    least_faculty=sorted(faculty_load,key=lambda x:x["load"])[:3]

    return render_template(
        "dashboard.html",
        rooms=len(rooms),
        faculty=len(faculty),
        schedules=len(schedules),
        students=students_today,
        utilization=utilization,
        faculty_capacity=faculty_capacity,
        room_util=room_util,
        underused_count=len(under_rooms),
        under_rooms=under_rooms,
        large_rooms=large_rooms,
        least_faculty=least_faculty
    )

# ---------------- AUTO END ----------------

@scheduler.task('interval', id='auto_end_classes', seconds=10)
def auto_end_classes():

    with app.app_context():

        now=datetime.now()
        sessions=Timetable.query.filter_by(status="ACTIVE").all()

        changed=False

        for s in sessions:
            if now>=datetime.combine(now.date(),s.end_time):
                s.status="ENDED"
                changed=True

        if changed:
            db.session.commit()
            socketio.emit("timetable_updated")

# ---------------- RUN ----------------

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
