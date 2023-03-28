### Run
 - load example_dags
 - run vscode with launch.json to test

### Version
 - apache/airflow:2.2.4
 - updated `CronTriggerTimetable`/`CronDataIntervalTimetable` move to plugins

### Reference
 - [apache/airflow](https://hub.docker.com/r/apache/airflow)  
 - [brki's answer](https://stackoverflow.com/questions/72478492/airflow-timetable-that-combines-multiple-cron-expressions)

### Running apache airflow 2.0 in docker with local executor.
Here are the steps to take to get airflow 2.0 running with docker on your machine. 
1. Create dags, logs and plugins folder inside the project directory
```bash
mkdir ./dags ./logs ./plugins ./example_dags
```
2. Launch airflow by docker-compose
```bash
docker-compose up -d
```
3. Check the running containers
```bash
docker ps
```
4. Open browser and type http://0.0.0.0:8098 to launch the airflow webserver

### Start
1. Create log folder
```bash
mkdir logs
```
2. Permission denied
```bash
chmod 777 ./dags/ ./plugins/ ./dags/ ./example_dags/
chmod +x functions/addconn.sh
chmod 666 functions/allconnections.csv
```
3. connection I/O
 - export connections
```bash
airflow@vm_airflow:/opt/airflow/dags/$dags test export_conn 2022-10-10
```
 - import connections
```bash
airflow@vm_airflow:/opt/airflow/dags/functions$./addconn.sh
```

![](images/screenshot_airflow_docker.png)