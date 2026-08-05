import hashlib
import os
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

import models  # noqa: F401
from database import Base, SessionLocal, engine
from models import Balance, MLModel, User, UserRole


def hash_password(password: str) -> str:
    """Создаёт хеш пароля с солью."""
    salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )

    return f"{salt.hex()}${password_hash.hex()}"


def create_user_if_missing(
    session: Session,
    login: str,
    password: str,
    role: UserRole,
    initial_balance: Decimal,
) -> User:
    user = session.scalar(select(User).where(User.login == login))

    if user is not None:
        return user

    user = User(
        login=login,
        password_hash=hash_password(password),
        role=role,
    )

    user.balance = Balance(amount=initial_balance)

    session.add(user)

    return user


def create_model_if_missing(
    session: Session,
    name: str,
    description: str,
    cost: Decimal,
) -> MLModel:
    ml_model = session.scalar(select(MLModel).where(MLModel.name == name))

    if ml_model is not None:
        return ml_model

    ml_model = MLModel(
        name=name,
        description=description,
        cost=cost,
    )

    session.add(ml_model)

    return ml_model


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        try:
            create_user_if_missing(
                session=session,
                login="demo_user",
                password="demo_user_password",
                role=UserRole.USER,
                initial_balance=Decimal("100.00"),
            )

            create_user_if_missing(
                session=session,
                login="demo_admin",
                password="demo_admin_password",
                role=UserRole.ADMIN,
                initial_balance=Decimal("1000.00"),
            )

            create_model_if_missing(
                session=session,
                name="sentiment-model",
                description="Модель анализа тональности текста",
                cost=Decimal("10.00"),
            )

            create_model_if_missing(
                session=session,
                name="faq-navigator",
                description="Модель поиска ответа в базе знаний",
                cost=Decimal("15.00"),
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print("База данных и демо-данные успешно инициализированы!")


if __name__ == "__main__":
    init_db()
