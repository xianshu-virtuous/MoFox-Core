# mmc/src/common/database/db_migration.py

from sqlalchemy import inspect
from sqlalchemy.schema import AddColumn, CreateIndex

from src.common.database.sqlalchemy_models import Base, get_engine
from src.common.logger import get_logger

logger = get_logger("db_migration")


async def check_and_migrate_database():
    """
    异步检查数据库结构并自动迁移。
    - 自动创建不存在的表。
    - 自动为现有表添加缺失的列。
    - 自动为现有表创建缺失的索引。
    """
    logger.info("正在检查数据库结构并执行自动迁移...")
    engine = await get_engine()

    async with engine.connect() as connection:
        # 在同步上下文中运行inspector操作
        def get_inspector(sync_conn):
            return inspect(sync_conn)

        inspector = await connection.run_sync(get_inspector)

        # 在同步lambda中传递inspector
        db_table_names = await connection.run_sync(lambda conn: set(inspector.get_table_names(conn)))

        # 1. 首先处理表的创建
        tables_to_create = []
        for table_name, table in Base.metadata.tables.items():
            if table_name not in db_table_names:
                tables_to_create.append(table)

        if tables_to_create:
            logger.info(f"发现 {len(tables_to_create)} 个不存在的表，正在创建...")
            try:
                # 一次性创建所有缺失的表
                await connection.run_sync(
                    lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables_to_create)
                )
                for table in tables_to_create:
                    logger.info(f"表 '{table.name}' 创建成功。")
                    db_table_names.add(table.name)  # 将新创建的表添加到集合中
            except Exception as e:
                logger.error(f"创建表时失败: {e}", exc_info=True)

        # 2. 然后处理现有表的列和索引的添加
        for table_name, table in Base.metadata.tables.items():
            if table_name not in db_table_names:
                logger.warning(f"跳过检查表 '{table_name}'，因为它在创建步骤中可能已失败。")
                continue

            logger.debug(f"正在检查表 '{table_name}' 的列和索引...")

            try:
                # 检查并添加缺失的列
                db_columns = await connection.run_sync(
                    lambda conn: {col["name"] for col in inspector.get_columns(table_name, conn)}
                )
                model_columns = {col.name for col in table.c}
                missing_columns = model_columns - db_columns

                if missing_columns:
                    logger.info(f"在表 '{table_name}' 中发现缺失的列: {', '.join(missing_columns)}")
                    async with connection.begin() as trans:
                        for column_name in missing_columns:
                            try:
                                column = table.c[column_name]
                                add_column_ddl = AddColumn(table_name, column)
                                await connection.execute(add_column_ddl)
                                logger.info(f"成功向表 '{table_name}' 添加列 '{column_name}'。")
                            except Exception as e:
                                logger.error(
                                    f"向表 '{table_name}' 添加列 '{column_name}' 失败: {e}",
                                    exc_info=True,
                                )
                                await trans.rollback()
                                break  # 如果一列失败，则停止处理此表的其他列
                else:
                    logger.info(f"表 '{table_name}' 的列结构一致。")

                # 检查并创建缺失的索引
                db_indexes = await connection.run_sync(
                    lambda conn: {idx["name"] for idx in inspector.get_indexes(table_name, conn)}
                )
                model_indexes = {idx.name for idx in table.indexes}
                missing_indexes = model_indexes - db_indexes

                if missing_indexes:
                    logger.info(f"在表 '{table_name}' 中发现缺失的索引: {', '.join(missing_indexes)}")
                    async with connection.begin() as trans:
                        for index_name in missing_indexes:
                            try:
                                index_obj = next((idx for idx in table.indexes if idx.name == index_name), None)
                                if index_obj is not None:
                                    await connection.execute(CreateIndex(index_obj))
                                    logger.info(f"成功为表 '{table_name}' 创建索引 '{index_name}'。")
                            except Exception as e:
                                logger.error(
                                    f"为表 '{table_name}' 创建索引 '{index_name}' 失败: {e}",
                                    exc_info=True,
                                )
                                await trans.rollback()
                                break  # 如果一个索引失败，则停止处理此表的其他索引
                else:
                    logger.debug(f"表 '{table_name}' 的索引一致。")

            except Exception as e:
                logger.error(f"在处理表 '{table_name}' 时发生意外错误: {e}", exc_info=True)
                continue

    logger.info("数据库结构检查与自动迁移完成。")
