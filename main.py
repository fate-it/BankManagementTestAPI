import io

import pandas as pd
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from database.models import build_db
from contextlib import asynccontextmanager
from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
import database.requests as db


@asynccontextmanager
async def lifespan(application: FastAPI):
    await build_db()
    print("Database tables created successfully")
    yield
    pass

app = FastAPI(lifespan=lifespan)


@app.get("/user_credits/{user_id}")
async def get_user_credits(user_id: int) -> list[dict]:
    """
    Отримати список кредитів користувача за його ID.

    :param user_id: Ідентифікатор користувача
    :return: Список словників з інформацією про кредити користувача
    :raises HTTPException 404: Якщо користувача не знайдено
    """
    user_credits = await db.get_credit_by_user_id(user_id)
    if not user_credits:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    credits_list = []
    for credit in user_credits:
        if credit.actual_return_date:
            loan_payment_amount = await db.get_loan_payment_amount_by_credit_id(credit.id)
            credits_list.append({
                "issuance_date": credit.issuance_date,
                "is_repaid": True,
                "actual_return_date": credit.actual_return_date,
                "body": credit.body,
                "percent": credit.percent,
                "loan_payment_amount": loan_payment_amount,
            })
        else:
            days_overdue = (credit.return_date - date.today()).days
            if days_overdue >= 0:
                days_overdue = 0
            else:
                days_overdue = abs(days_overdue)
            credits_list.append({
                "issuance_date": credit.issuance_date,
                "is_repaid": False,
                "return_date": credit.return_date,
                "days_overdue": days_overdue,
                "today": date.today(),
                "body": credit.body,
                "percent": credit.percent,
                "sum_body_payments": await db.get_credit_payments_by_type(credit.id, 1),
                "sum_percent_payments": await db.get_credit_payments_by_type(credit.id, 2),
            })
    return credits_list


@app.post("/plans_insert", summary="Метод для завантаження планів на новий місяць")
async def upload_plans(file: UploadFile = File(...)):
    """
    Завантажує плани на новий місяцю з Excel-файлу.

    Вимоги:
    - Файл повинен вміщувати колонки: period (перше число місяця), sum, category_name
    - Сума не може бути пустою (0 дозволено)
    - План з таким місяцем і категорыэю не повинен ыснувати в БД
    """

    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="Файл повинен бути у форматі Excel (.xls, .xlsx)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        required_columns = ['period', 'sum', 'category_name']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            raise HTTPException(
                status_code=400,
                detail=f"В файлі відсутні обов'язкові колонки: {', '.join(missing)}"
            )

        errors = []
        plans_to_insert = []

        for index, row in df.iterrows():
            if isinstance(row['period'], datetime):
                period_date = row['period'].date()
            elif isinstance(row['period'], date):
                period_date = row['period']
            else:
                errors.append(f"Рядок {index + 1}: Некоректний формат дати")
                continue

            if period_date.day != 1:
                errors.append(f"Рядок {index + 1}: Дата повинна бути першим числом місяця")
                continue

            if pd.isna(row['sum']):
                errors.append(f"Рядок {index + 1}: Сума не может бути пустой")
                continue

            try:
                amount = Decimal(str(row['sum'])).quantize(Decimal('0.00'))
            except:
                errors.append(f"Рядок {index + 1}: Некоректне значення суми")
                continue

            category_name = str(row['category_name']).strip()
            category_id = await db.get_category_id_by_name(category_name)

            if not category_id:
                errors.append(f"Рядок {index + 1}: Катігорія '{category_name}' не знайдена")
                continue

            existing_plan = await db.get_plan_by_date_and_category(period_date, category_id)

            if existing_plan:
                errors.append(
                    f"Рядок {index + 1}: План на {period_date.strftime('%Y-%m-%d')} для категорії '{category_name}' вже існує")
                continue

            plans_to_insert.append({"period": period_date, "sum": amount, "category_id": category_id})

        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        await db.bulk_insert_plans(plans_to_insert)

        return JSONResponse(
            status_code=200,
            content={"message": f"Успішно додано {len(plans_to_insert)} записів в БД"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка обробки файлу: {str(e)}")


@app.get("/plans_performance/{date_str}") #DD-MM-YYYY
async def get_all_performance(date_str: str) -> list[dict]:
    """
     Отримати інформацію про виконання планів за вказану дату.

    :param date_str: Дата у форматі DD-MM-YYYY
    :return: Список словників з інформацією про кожен план
    :raises HTTPException 400: Якщо передано дату в некоректному форматі
    :raises HTTPException 404: Якщо на відповідний місяць не знайдено жодного плану
    """
    try:
        date_obj = datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Невірний формат дати. Очікується формат DD-MM-YYYY.")

    actual_month = date(date_obj.year, date_obj.month, 1)
    plans = await db.get_month_plans(actual_month)
    if not plans:
        raise HTTPException(status_code=404, detail="На поточний місяць ще не заплановано жодного плану. "
                                                    "Створіть плани для перегляду виконання.")
    plan_status = []
    for plan in plans:
        category = await db.get_category_name_by_id(plan.category_id)
        if category == "видача":
            sum_issued_loans = await db.get_sum_issued_loans(plan.period, date_obj)
            plan_status.append({
                "period": plan.period,
                "category": category,
                "plan_sum": plan.sum,
                "sum_issued_loans": sum_issued_loans,
                "plan_completion_rate": str(round(sum_issued_loans*100/(plan.sum or 1), 2))+"%"
            })
        elif category == "збір":
            payment_sum = await db.get_payment_sum(plan.period, date_obj)
            plan_status.append({
                "period": plan.period,
                "category": category,
                "plan_sum": plan.sum,
                "payment_sum": payment_sum,
                "plan_completion_rate": str(round(payment_sum*100/(plan.sum or 1), 2))+"%"
            })
    return plan_status


@app.get("/year_performance/{year}")
async def get_year_performance(year: int) -> list[dict]:
    """
    Отримати інформацію про виконання планів за вказаний рік.

    :param year: Рік
    :return: Список словників з інформацією про кожен місячний план
    """
    year_status = []
    sum_issues_of_year = 0
    sum_payments_of_year = 0
    plans = await db.get_year_plans(int(year))
    if not plans:
        raise HTTPException(status_code=404, detail="На поточний рік ще не заплановано жодного плану. "
                                                    "Створіть плани для перегляду виконання.")

    for plan_date, plans_list in plans.items():
        for plan in plans_list:
            if plan.category_id == await db.get_category_id_by_name("видача"):
                sum_issues_of_year += ((await db.get_month_sum_issued_loans(plan_date)) or 0)
            else:
                sum_payments_of_year += ((await db.get_month_sum_payments(plan_date)) or 0)
    for plan_date, plans_list in plans.items():
        issued_loans_count = 0
        payments_count = 0
        plan_sum_issued_loans = 0
        plan_sum_payments = 0
        sum_issued_loans = 0
        sum_payments = 0
        for plan in plans_list:
            if plan.category_id == await db.get_category_id_by_name("видача"):
                issued_loans_count = issued_loans_count + await db.get_amount_of_loans(plan_date)
                plan_sum_issued_loans = plan.sum
                sum_issued_loans = (await db.get_month_sum_issued_loans(plan_date)) or 0
            else:
                payments_count = payments_count + await db.get_amount_of_payments(plan_date)
                plan_sum_payments = plan.sum
                sum_payments = (await db.get_month_sum_payments(plan_date)) or 0
        year_status.append({
            "date": plan_date.strftime("%m.%Y"),
            "issued_loans_count": issued_loans_count,
            "plan_sum_issued_loans": plan_sum_issued_loans,
            "sum_issued_loans": sum_issued_loans,
            "plan_issued_completion_rate": str(round(sum_issued_loans * 100 / plan_sum_issued_loans, 2)) + "%",
            "payments_count": payments_count,
            "plan_sum_payments": plan_sum_payments,
            "sum_payments": sum_payments,
            "plan_payments_completion_rate": str(round(sum_payments * 100 / plan_sum_payments, 2)) + "%",
            "monthly_issued_percent_of_year": str(round(sum_issued_loans * 100 / (sum_issues_of_year or 1), 2)) + "%",
            "monthly_payment_percent_of_year": str(round(sum_payments * 100 / (sum_payments_of_year or 1), 2)) + "%",
        })
    return year_status


if __name__ == "__main__":
    uvicorn.run("main:app")
