from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            native_enum=False,
            validate_strings=True,
        ),
        default=UserRole.USER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    balance: Mapped[Balance] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list[MLTask]] = relationship(
        back_populates="user",
        uselist=True,
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user",
    )


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="ck_balances_amount_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    user: Mapped[User] = relationship(
        back_populates="balance",
    )


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        CheckConstraint(
            "cost >= 0",
            name="ck_ml_models_cost_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    tasks: Mapped[list[MLTask]] = relationship(
        back_populates="model",
    )


class MLTask(Base):
    __tablename__ = "ml_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id"),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    input_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    charged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="tasks",
    )
    model: Mapped[MLModel] = relationship(
        back_populates="tasks",
    )
    result: Mapped[PredictionResult | None] = relationship(
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
    )
    transaction: Mapped[Transaction | None] = relationship(
        back_populates="task",
        uselist=False,
    )


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("ml_tasks.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    prediction_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    invalid_rows: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped[MLTask] = relationship(
        back_populates="result",
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_transactions_amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_tasks.id"),
        unique=True,
        nullable=True,
    )
    operation_type: Mapped[TransactionType] = mapped_column(
        SqlEnum(
            TransactionType,
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(
        back_populates="transactions",
    )
    task: Mapped[MLTask | None] = relationship(
        back_populates="transaction",
    )
