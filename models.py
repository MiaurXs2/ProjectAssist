from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///example.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("gitlab", ForeignKey("User.gitlab"), primary_key=True),
    Column("role", ForeignKey("Roles.role"), primary_key=True)
)

class Role(Base):
    __tablename__ = "Roles"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, unique=True, nullable=False)
    users = relationship("User", secondary="user_roles", back_populates="roles")


class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True, index=True)
    gitlab = Column(String, unique=True, nullable=True)
    tg_id = Column(Integer, unique=False, index=True)
    roles = relationship("Role", secondary="user_roles", back_populates="users")
