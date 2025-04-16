from sqlalchemy import (ForeignKey, PrimaryKeyConstraint, String, BigInteger,
                        Integer, TIMESTAMP, Date, CHAR, func, text, DECIMAL)
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime, date
from database.engine import engine
from decimal import Decimal


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(50), nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, default=date.today)


class Credit(Base):
    __tablename__ = 'credits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    issuance_date: Mapped[date] = mapped_column(Date, default=date.today)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_return_date: Mapped[date] = mapped_column(Date, nullable=True)
    body: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    percent: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)


class Dictionary(Base):
    __tablename__ = 'dictionaries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Plan(Base):
    __tablename__ = 'plans'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[date] = mapped_column(Date, nullable=False) #перше число місяця
    sum: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('dictionaries.id'), nullable=False)


class Payment(Base):
    __tablename__ = 'payments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sum: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_id: Mapped[int] = mapped_column(Integer, ForeignKey('credits.id'))
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey('dictionaries.id'))


async def build_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
