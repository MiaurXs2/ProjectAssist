from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///example.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

developer_reviewer = Table(
    "developer_reviewer",
    Base.metadata,
    Column("developer", ForeignKey("User.gitlab")),
    Column("reviewer", ForeignKey("User.gitlab")),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("gitlab", ForeignKey("User.gitlab")),
    Column("role", ForeignKey("Roles.role"))
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
    reviewers = relationship(
        "User",
        secondary=developer_reviewer,
        primaryjoin=gitlab == developer_reviewer.c.developer,
        secondaryjoin=gitlab == developer_reviewer.c.reviewer,
        back_populates="developers"
    )
    developers = relationship(
        "User",
        secondary=developer_reviewer,
        primaryjoin=gitlab == developer_reviewer.c.reviewer,
        secondaryjoin=gitlab == developer_reviewer.c.developer,
        back_populates="reviewers"
    )