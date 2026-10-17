"""Isolated synthetic data: run only in disposable benchmark PostgreSQL."""
from datetime import timedelta
from app.database import DBSession, User, Session, utcnow
from app.departments import AcademicDepartment
from app.student_models import BCAStudent, StudentCase
from app.student_profiles import StudentShowcase
from app.security import hash_secret, hash_password

USERS = 150
PHOTOBYTES = 40000

def token_for(i):
    return f"ncet-local-load-benchmark-session-{i:03d}-20261017"

def csrf_for(i):
    return f"synthetic-csrf-{i:03d}-only"

def main():
    with DBSession() as db:
        assert db.query(User.id).count() == 0, "Database must be brand-new; refusing to replace accounts."
        db.add(AcademicDepartment(code="Computer Applications",name="Computer Applications",active=True))
        db.flush()
        pwd_hash=hash_password("Benchmark-Password-Not-For-Production-2026!")
        db.add(User(username="hodbench",display_name="Test HOD",role="hod",
                    department="Computer Applications",active=True,password_hash=pwd_hash))
        for i in range(USERS):
            usn=f"1NC24BCA{i:03d}"
            student=User(username=usn.lower(),display_name=f"Synthetic Student {i:03d}",
                         role="student",department="Computer Applications",
                         active=True,password_hash=pwd_hash)
            db.add(student)
            db.flush()
            db.add(BCAStudent(user_id=student.id,usn=usn,semester=3,
                              must_change_password=False))
            db.add(StudentShowcase(student_id=student.id,published=i<120,
                    about="Student participation in academic and campus collaborations. "*3,
                    skills_json='["Python","C","JavaScript","SQL","React","AI"]',
                    interests_json='["Software Engineering","Artificial Intelligence"]',
                    certificates_json='[]',projects_json='[]',social_links_json='{}',
                    photo_mime="image/webp" if i<100 else None,
                    photo_bytes=(b"x"*PHOTOBYTES) if i<100 else None))
            db.add(Session(user_id=student.id,token_hash=hash_secret(token_for(i)),
                           csrf_token=csrf_for(i),expires_at=utcnow()+timedelta(hours=8)))
            for j in range(2):
                db.add(StudentCase(reference=f"NCET-BCA-BENCH-{i:03d}-{j}",
                    student_id=student.id,department="Computer Applications",
                    category="academics",subject=f"Academic query {i}-{j}",
                    description="Synthetic test request about the semester timetable.",
                    status="submitted"))
        db.commit()
        print(f"SEED: {USERS} students, 120 published profiles, 100 simulated photos (40 KB each), {USERS*2} private cases, {USERS} sessions, 1 HOD. Database: disposable, no real student data.",flush=True)

if __name__=="__main__":main()
