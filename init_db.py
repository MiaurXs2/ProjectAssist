from models import Base, engine, SessionLocal, Role

def init_db():
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    roles = ["админ", "разработчик", "тимлид", "тестировщик"]

    for r in roles:
        if not session.query(Role).filter_by(role=r).first():
            session.add(Role(role=r))

    session.commit()
    session.close()

if __name__ == "__main__":
    init_db()