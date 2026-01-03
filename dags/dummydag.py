from airflow import DAG
from airflow.decorators import dag
from airflow.operators.empty import EmptyOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime

PROJECT_HOME = os.getenv("PROJECT_HOME")

def prints():
    timestamp = int(datetime.time())
    PROJECT_HOME_VAR = os.getenv("PROJECT_HOME")
    # Print the timestamp
    print("Current timestamp:", timestamp)
    print("PROJECT_HOME_VAR:", PROJECT_HOME_VAR)

with DAG(
    dag_id="dag1",
    description="dag1",
    start_date=datetime(2022, 10, 31),
    schedule_interval="@once",
) as dag1:
    op = EmptyOperator(task_id="dummy")


dag2 = DAG(
    dag_id="dag2",
    description="2dag2",
    start_date=datetime(2022, 10, 31),
    schedule_interval="@once",
)
op2 = EmptyOperator(task_id="dummy2", dag=dag2)


@dag(
    dag_id="dag3",
    description="dag3",
    start_date=datetime(2022, 10, 31),
    schedule_interval="@once",
)
def generate_dag():
    op3 = EmptyOperator(task_id="dummy3")


dag3 = generate_dag()



with DAG(dag_id='A_dag_mixed', schedule_interval='@once', start_date=datetime(2022, 7, 1)) as dag:
    t1 = BashOperator(task_id='primer_task_bash',
                      bash_command='echo "Hola mundo"')
    
    t2 = BashOperator(task_id='segundo_task_bash',
                      bash_command='echo $PROJECT_HOME',)
    t3 = PythonOperator(task_id='task1',
                      python_callable=prints
                      )