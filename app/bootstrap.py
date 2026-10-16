"""One-time bootstrap. No default passwords, passwords must be set via private environment variables."""
import os
from sqlalchemy.exc import IntegrityError
from .database import DBSession, User
from .security import hash_password

DEFAULT_DEPARTMENT='Computer Science & Engineering'
ROLES={
    'admin': 'System Administrator',
    'principal': 'Office of the Principal',
    'hod': 'Head of Department',
    'staff': 'Faculty Member',
    'iqac': 'IQAC Coordinator',
}


def main():
    with DBSession() as db:
        for role,name in ROLES.items():
            value = os.environ.get(f'NCET_BOOTSTRAP_{role.upper()}_PASSWORD')
            username = os.environ.get(f'NCET_BOOTSTRAP_{role.upper()}_USERNAME', role)
            if not value:
                continue
            if db.query(User).filter(User.username == username).first():
                print(f'{role}: account exists; bootstrap did not reset its password')
                continue
            u=User(username=username, display_name=name, role=role,department=DEFAULT_DEPARTMENT,
                   password_hash=hash_password(value))
            db.add(u)
            db.commit()
            print(f'Created {role} account: {username}')

if __name__=='__main__': main()
