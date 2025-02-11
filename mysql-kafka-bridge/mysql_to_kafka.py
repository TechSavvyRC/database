import mysql.connector
import logging
import time
import os
import sys
import json
from confluent_kafka import Producer
from datetime import datetime
from decimal import Decimal

# Logging configuration - Changed to log to stdout for container compatibility
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def get_required_env_var(var_name):
    """
    Retrieve and validate required environment variables
    """
    value = os.getenv(var_name)
    if value is None:
        logger.error(f"Required environment variable {var_name} is not set")
        sys.exit(1)
    return value

def get_configs():
    """
    Retrieve all configuration from environment variables with validation
    """
    # Required environment variables
    required_vars = [
        'MYSQL_HOST',
        'MYSQL_USER',
        'MYSQL_PASSWORD',
        'MYSQL_DATABASE',
        'KAFKA_BOOTSTRAP_SERVERS'
    ]

    # Validate all required variables are present
    for var in required_vars:
        get_required_env_var(var)

    mysql_config = {
        'host': get_required_env_var('MYSQL_HOST'),
        'user': get_required_env_var('MYSQL_USER'),
        'password': get_required_env_var('MYSQL_PASSWORD'),
        'database': get_required_env_var('MYSQL_DATABASE')
    }

    kafka_config = {
        'bootstrap.servers': get_required_env_var('KAFKA_BOOTSTRAP_SERVERS'),
        'queue.buffering.max.messages': int(os.getenv('KAFKA_MAX_MESSAGES', '10000')),
        'queue.buffering.max.kbytes': int(os.getenv('KAFKA_MAX_KBYTES', '104857')),
        'message.timeout.ms': 30000,
        #'debug': 'broker,topic,msg',
        'error_cb': kafka_error_callback
    }

    return mysql_config, kafka_config

def kafka_error_callback(err):
    """
    Callback function for Kafka errors
    """
    logger.error(f'Kafka error: {err}')

def test_connections(mysql_config, kafka_config):
    """
    Test both MySQL and Kafka connections before starting the main loop
    """
    # Test MySQL connection
    try:
        connection = mysql.connector.connect(**mysql_config)
        logger.info("Successfully connected to MySQL")
        connection.close()
    except mysql.connector.Error as e:
        logger.error(f"Failed to connect to MySQL: {e}")
        return False

    # Test Kafka connection
    try:
        producer = Producer(kafka_config)
        producer.list_topics(timeout=5)
        logger.info("Successfully connected to Kafka")
        producer.flush(timeout=10)
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        return False

    return True

def save_last_timestamp(timestamp):
    """
    Save the last processed timestamp to a persistent location
    """
    try:
        with open("/app/last_timestamp.txt", "w") as file:
            file.write(timestamp)
        logger.debug(f"Saved timestamp: {timestamp}")
    except Exception as e:
        logger.error(f"Error saving timestamp: {e}")

def load_last_timestamp(mysql_config):
    """
    Load the last processed timestamp from persistent storage
    """
    try:
        with open("/app/last_timestamp.txt", "r") as file:
            timestamp = file.read().strip()
            logger.debug(f"Loaded timestamp: {timestamp}")
            return timestamp
    except FileNotFoundError:
        # If no file exists, fetch the earliest timestamp from the database
        logger.info("No timestamp file found. Fetching earliest timestamp from database...")
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(**mysql_config)
            cursor = connection.cursor()
            query = "SELECT MAX(timestamp) FROM ecom_transactions"
            cursor.execute(query)
            result = cursor.fetchone()
            earliest_timestamp = result[0]

            if earliest_timestamp is None:
                # If the table is empty, start from the current time
                default_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"No records found in database. Starting from: {default_timestamp}")
                return default_timestamp

            logger.info(f"Earliest timestamp in database: {earliest_timestamp}")
            return earliest_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.error(f"Error fetching earliest timestamp from database: {e}")
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

def fetch_new_records(mysql_config, last_timestamp):
    """
    Fetch new records from MySQL with error handling and connection management
    """
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT * FROM ecom_transactions 
            WHERE timestamp > %s 
            ORDER BY timestamp ASC 
        """
        cursor.execute(query, (last_timestamp,))
        records = cursor.fetchall()
        logger.info(f"Fetched {len(records)} new records")
        return records
    except mysql.connector.Error as e:
        logger.error(f"Error fetching records from MySQL: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def produce_to_kafka(records, producer, topic):
    """
    Produce records to Kafka with enhanced error handling
    """
    success_count = 0
    for record in records:
        try:
            # Convert datetime objects to string for JSON serialization
            record_copy = record.copy()
            for key, value in record_copy.items():
                if isinstance(value, datetime):
                    record_copy[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, Decimal):
                    record_copy[key] = float(value)

            # Produce message to Kafka
            producer.produce(
                topic,
                key=str(record['transaction_id']),
                value=json.dumps(record_copy),
                callback=delivery_report
            )
            logger.info(f"Record sent to Kafka: {record['transaction_id']}, {record['timestamp']}")
            success_count += 1
        except Exception as e:
            logger.error(f"Error sending record {record['transaction_id']} to Kafka: {e}")
    
    logger.info(f"Successfully produced {success_count} records to Kafka")
    return success_count

def delivery_report(err, msg):
    """
    Callback for Kafka message delivery reports
    """
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}]')

def main():
    """
    Main function with enhanced error handling and connection management
    """
    # Get configurations
    try:
        mysql_config, kafka_config = get_configs()
    except Exception as e:
        logger.error(f"Failed to get configurations: {e}")
        sys.exit(1)

    # Test connections before starting
    if not test_connections(mysql_config, kafka_config):
        logger.error("Failed to establish required connections. Exiting...")
        sys.exit(1)

    kafka_topic = os.getenv('KAFKA_TOPIC', 'ecom_transactions')
    producer = Producer(kafka_config)
    last_timestamp = load_last_timestamp(mysql_config)

    logger.info("Starting main processing loop...")
    while True:
        try:
            # Fetch new records from MySQL
            records = fetch_new_records(mysql_config, last_timestamp)

            if records:
                # Produce records to Kafka
                success_count = produce_to_kafka(records, producer, kafka_topic)
                
                if success_count > 0:
                    # Update the last timestamp only if we successfully produced messages
                    last_timestamp = records[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    save_last_timestamp(last_timestamp)

                # Flush Kafka producer buffer
                producer.flush(timeout=10)

            time.sleep(60)  # Wait for 1 minute before next fetch

        except KeyboardInterrupt:
            logger.info("Received shutdown signal. Cleaning up...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(60)  # Wait before retrying

    # Cleanup
    producer.flush(timeout=10)
    #producer.close()
    logger.info("Shutdown complete")

if __name__ == "__main__":
    main()

