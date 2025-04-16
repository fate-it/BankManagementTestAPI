from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from config import DB_URL

engine = create_async_engine(url=DB_URL, echo=True)


async_session = async_sessionmaker(engine, expire_on_commit=False)
