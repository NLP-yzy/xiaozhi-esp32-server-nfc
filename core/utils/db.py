import aiomysql
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MySQLPool:
    _instance = None
    _pool = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls, config):
        """初始化数据库连接池"""
        if not cls._pool:
            try:
                cls._pool = await aiomysql.create_pool(
                    host=config['host'],
                    port=config['port'],
                    user=config['user'],
                    password=config['password'],
                    db=config['database'],
                    minsize=1,
                    maxsize=10,
                    autocommit=True
                )
                logger.bind(tag=TAG).info("MySQL connection pool initialized")
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to initialize MySQL pool: {str(e)}")
                raise

    @classmethod
    async def get_pool(cls):
        """获取连接池"""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
        return cls._pool

    @classmethod
    async def close(cls):
        """关闭连接池"""
        if cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed()
            cls._pool = None