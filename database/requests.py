from collections import defaultdict

from fastapi import HTTPException

from database.engine import async_session
from sqlalchemy import select, delete as del_el, update, func, text
from database.models import User, Credit, Plan, Payment, Dictionary
from datetime import date

def connection(func_decor):
    async def inner(*args, **kwargs):
        async with async_session() as session:
            return await func_decor(session, *args, **kwargs)
    return inner


@connection
async def get_credit_by_user_id(session, user_id):
    return (await session.scalars(select(Credit).where(Credit.user_id == user_id))).all()


@connection
async def get_loan_payment_amount_by_credit_id(session, credit_id):
    return (await session.scalar(select(func.sum(Payment.sum)).where(Payment.credit_id == credit_id))) or 0


@connection
async def get_credit_payments_by_type(session, credit_id, type_id):
    return (await session.scalar(select(func.sum(Payment.sum)).where(
        Payment.type_id == type_id, Payment.credit_id == credit_id))) or 0


@connection
async def get_category_id_by_name(session, category_name):
    return await session.scalar(select(Dictionary.id).where(Dictionary.name == category_name))


@connection
async def get_plan_by_date_and_category(session, period_date, category_id):
    return (await session.scalars(select(Plan).where(
        Plan.period == period_date, Plan.category_id == category_id))).first()


@connection
async def bulk_insert_plans(session, plans):
    try:
        for plan_data in plans:
            plan = Plan(**plan_data)
            session.add(plan)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении в БД: {str(e)}")


@connection
async def get_month_plans(session, today_date):
    return (await session.scalars(select(Plan).where(
        Plan.period == today_date
    ))).all()


@connection
async def get_category_name_by_id(session, category_id):
    return await session.scalar(select(Dictionary.name).where(
        Dictionary.id == category_id
    ))


@connection
async def get_sum_issued_loans(session, period, actual_date):
    return await session.scalar(select(func.sum(Credit.body)).where(
        Credit.issuance_date >= period, Credit.issuance_date <= actual_date
    ))


@connection
async def get_month_sum_issued_loans(session, period):
    return await session.scalar(select(func.sum(Credit.body)).where(
        Credit.issuance_date >= period, Credit.issuance_date < incr_month(period)
    ))


@connection
async def get_month_sum_payments(session, plan_date):
    return await session.scalar(select(func.sum(Payment.sum)).where(
        Payment.payment_date >= plan_date, Payment.payment_date < incr_month(plan_date)
    ))


@connection
async def get_payment_sum(session, period, actual_date):
    return await session.scalar(select(func.sum(Payment.sum)).where(
        Payment.payment_date >= period, Payment.payment_date <= actual_date
    ))


@connection
async def get_year_plans(session, year: int):
    plans = (await session.scalars(select(Plan).where(
        Plan.period >= date(year, 1, 1), Plan.period <= date(year, 12, 1)
    ).order_by(Plan.period))).all()
    grouped = defaultdict(list)
    for plan in plans:
        grouped[plan.period].append(plan)

    return grouped


@connection
async def get_amount_of_loans(session, plan_date):
    return await session.scalar(select(func.count()).where(
        Credit.issuance_date >= plan_date, Credit.issuance_date < incr_month(plan_date)
    ))


@connection
async def get_amount_of_payments(session, plan_date):
    return await session.scalar(select(func.count()).where(
        Payment.payment_date >= plan_date, Payment.payment_date < incr_month(plan_date)
    ))


def incr_month(plan_date):
    if plan_date.month == 12:
        month = 1
        year = plan_date.year+1
    else:
        month = plan_date.month+1
        year = plan_date.year
    return date(year, month, 1)