from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class NFCDao:
    def __init__(self, pool):
        self.pool = pool

    async def get_role_by_nfc(self, nfc_info: str, device_input: str) -> str:
        """
        根据NFC信息和设备ID获取对应的角色信息
        :param nfc_info: NFC卡号
        :param device_input: 输入的设备ID
        :return: 角色信息
        """
        async with self.pool.acquire() as conn_sql:
            async with conn_sql.cursor() as cursor:
                try:
                    # 查询NFC卡对应的角色和设备ID
                    await cursor.execute(
                        "SELECT role_info, device_id FROM nfc_role WHERE nfc_info = %s",
                        (nfc_info,)
                    )
                    result = await cursor.fetchone()
                    
                    if not result:
                        return "1"
                    
                    role_info, device_id = result
                    
                    # 如果设备ID为空，更新设备ID
                    if device_id is None:
                        await cursor.execute(
                            "UPDATE nfc_role SET device_id = %s WHERE nfc_info = %s",
                            (device_input, nfc_info)
                        )
                        await conn_sql.commit()
                        return role_info
                    
                    # 如果设备ID与输入的设备ID匹配
                    if device_id == device_input:
                        return role_info
                    
                    # 其他情况返回default
                    return "1"
                    
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Database error: {str(e)}")
                    return "1"