import json
from raw.connect_settings import conn, engine
conn.autocommit = False
import psycopg2
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.bash_operator import BashOperator
import logging as log
from logging import handlers
from airflow.models import Variable
from datetime import datetime, timedelta
import time
from airflow.utils.log.logging_mixin import LoggingMixin
import os
from sqlalchemy import create_engine
from core.ddl_core import DatabaseManager
from core.dml_core import DataManager
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raw.get_match import GetMatchJobParser, table_name
from raw.variables_settings import variables, base_getmatch
from core.model_spacy import DataPreprocessing
from core.base_dag import BaseDags


log.basicConfig(
    format='%(threadName)s %(name)s %(levelname)s: %(message)s',
    level=log.INFO
)

# Default dag arguments
default_args = {
    "owner": "admin_1T",
    'start_date': datetime(2023, 11, 26),
    'retry_delay': timedelta(minutes=5),
}


class Dags(BaseDags):
    def run_init_getmatch_parser(self):
        """
        Основной вид задачи для запуска парсера для вакансий GetMatch
        """
        log.info('Запуск парсера GetMatch')
        try:
            parser = GetMatchJobParser(base_getmatch, log, conn, table_name)
            parser.find_vacancies()
            parser.addapt_numpy_null()
            parser.save_df()
            log.info('Парсер GetMatch успешно провел работу')
            self.df = parser.df
        except Exception as e:
            log.error(f'Ошибка во время работы парсера GetMatch: {e}')

    def run_update_getmatch(self):
        parser = GetMatchJobParser(base_getmatch, log, conn, table_name)
        parser.find_vacancies()
        parser.generating_dataframes()
        parser.addapt_numpy_null()
        parser.update_database_queries()
        self.dataframe_to_update = parser.dataframe_to_update
        self.dataframe_to_closed = parser.dataframe_to_closed

def init_call_all_func():
    worker = Dags()
    worker.run_init_getmatch_parser()
    worker.model(worker.df)
    worker.dml_core_init(worker.dfs)

def update_call_all_func():
    worker = Dags()
    worker.run_update_getmatch()
    worker.update_dicts()
    worker.model(worker.dataframe_to_update)
    worker.dml_core_update_and_archivate(worker.dfs, worker.dataframe_to_closed)


with DAG(
        dag_id="init_getmatch_parser",
        schedule_interval=None, tags=['admin_1T'],
        default_args=default_args,
        catchup=False
) as dag_initial:
    parse_get_match_jobs = PythonOperator(
        task_id='init_getmatch_task',
        python_callable=init_call_all_func,
        provide_context=True
    )

with DAG(
        dag_id="update_getmatch_parser",
        schedule_interval=None, tags=['admin_1T'],
        default_args=default_args,
        catchup=False
) as getmatch_update_dag:
    parse_delta_getmatch_jobs = PythonOperator(
        task_id='update_getmatch_task',
        python_callable=update_call_all_func,
        provide_context=True
    )


# ddl_dag = DAG(dag_id='core_ddl_dag',
#               tags=['admin_1T'],
#               start_date=datetime(2023, 11, 25),
#               schedule_interval=None,
#               default_args=default_args
#               )
#
# dml_init_dag = DAG(dag_id='core_dml_init_dag',
#               tags=['admin_1T'],
#               start_date=datetime(2023, 11, 25),
#               schedule_interval=None,
#               default_args=default_args
#               )
#
# hello_bash_task = BashOperator(
#     task_id='hello_task',
#     bash_command='echo "Удачи"'
# )
#
# end_task = DummyOperator(
#     task_id="end_task"
# )
#
# create_golden_core = PythonOperator(
#     task_id='create_core_tables',
#     python_callable=ddl_core,
#     provide_context=True,
#     dag=ddl_dag
# )
#
# init_golden_core = PythonOperator(
#     task_id='create_core_tables',
#     python_callable=dml_core,
#     provide_context=True,
#     dag=dml_init_dag
# )
#
# hello_bash_task >> create_golden_core >> end_task
# init_golden_core
#
#
# with DAG(dag_id="initial_getmatch_parser",
#          schedule_interval=None, tags=['admin_1T'],
#          default_args=default_args,
#          catchup=False) as dag_initial_getmatch_parser:
#     parse_get_match_jobs = PythonOperator(
#         task_id='init_run_getmatch_parser_task',
#         python_callable=run_init_getmatch_parser,
#         provide_context=True)
#
# parse_get_match_jobs