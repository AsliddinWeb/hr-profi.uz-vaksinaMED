import app.models  # noqa: F401  (jadvallarni Base.metadata ga ro'yxatdan o'tkazadi)
from app.db import Base
from app.migrations_env import run

run(Base.metadata)
