## Add quote_plus to sign the original string are escaped  
 - Mongo hook be replaced
 - ${AIRFLOW_HOME}/lib/python3.7/site-packages/airflow/providers/mongo/hooks/
    ```bash
    self.connection.password  
    ```
    to
    ```bash
    quote_plus(self.connection.password)  
    ```

