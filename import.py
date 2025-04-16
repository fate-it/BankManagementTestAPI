import pandas as pd
from sqlalchemy import create_engine
import re

# Чтение CSV-файла
df = pd.read_csv('content/payments.csv', sep='[ \t]')

df['payment_date'] = pd.to_datetime(df['payment_date'], format='%d.%m.%Y')
# df['return_date'] = pd.to_datetime(df['return_date'], format='%d.%m.%Y')
# df['actual_return_date'] = pd.to_datetime(df['actual_return_date'], format='%d.%m.%Y', errors='coerce')

engine = create_engine("mysql+pymysql://root:root@localhost/creditdb")

# Запись данных в БД
df.to_sql('payments', con=engine, if_exists='append', index=False)
