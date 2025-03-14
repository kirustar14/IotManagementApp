import datetime
import os
import time
import logging
import mysql.connector

from typing import Optional
from dotenv import load_dotenv
from mysql.connector import Error
import uuid

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Custom exception for database connection failures"""
    pass


def get_db_connection(
    max_retries: int = 12,  # 12 retries = 1 minute total (12 * 5 seconds)
    retry_delay: int = 5,  # 5 seconds between retries
) -> mysql.connector.MySQLConnection:
    """Create database connection with retry mechanism."""
    connection: Optional[mysql.connector.MySQLConnection] = None
    attempt = 1
    last_error = None

    while attempt <= max_retries:
        try:
            connection = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST"),
                user=os.getenv("MYSQL_USER"),
                port=os.getenv("MYSQL_PORT"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=os.getenv("MYSQL_DATABASE"),
            )

            # Test the connection
            connection.ping(reconnect=True, attempts=1, delay=0)
            logger.info("Database connection established successfully")
            return connection

        except Error as err:
            last_error = err
            logger.warning(
                f"Connection attempt {attempt}/{max_retries} failed: {err}. "
                f"Retrying in {retry_delay} seconds..."
            )

            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

            if attempt == max_retries:
                break

            time.sleep(retry_delay)
            attempt += 1

    raise DatabaseConnectionError(
        f"Failed to connect to database after {max_retries} attempts. "
        f"Last error: {last_error}"
    )

async def setup_database(initial_users: dict = None):
    """Creates user and session tables and populates initial user data if provided."""
    connection = None
    cursor = None

# Define table schemas
    table_schemas = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                location VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "sessions": """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """,
        "wardrobe": """
            CREATE TABLE IF NOT EXISTS wardrobe (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                item_name VARCHAR(255) NOT NULL,
                item_description TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """, 
        "devices": """
            CREATE TABLE IF NOT EXISTS devices (
                device_id CHAR(36) PRIMARY KEY,  -- Use UUID() for device_id
                user_id INTEGER NOT NULL,
                device_name VARCHAR(255),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """, 
        "temperature": """
            CREATE TABLE IF NOT EXISTS temperature (
                id INT AUTO_INCREMENT PRIMARY KEY,
                value FLOAT,
                unit VARCHAR(10),
                timestamp DATETIME,
                device_id CHAR(36),
                FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
            )
        """
    } 

    try:
        # Get database connection
        connection = get_db_connection()
        cursor = connection.cursor()


        # Recreate tables one by one
        for table_name, create_query in table_schemas.items():
            try:
                # Create table
                logger.info(f"Creating table {table_name}...")
                cursor.execute(create_query)
                connection.commit()
                logger.info(f"Table {table_name} created successfully")
            except Error as e:
                logger.error(f"Error creating table {table_name}: {e}")
                raise

        # Insert initial users if provided
        if initial_users:
            try:
                insert_query = "INSERT INTO users (name, password) VALUES (%s, %s)"
                for name, password in initial_users.items():
                    cursor.execute(insert_query, (name, password))
                connection.commit()
                logger.info(f"Inserted {len(initial_users)} initial users")
            except Error as e:
                logger.error(f"Error inserting initial users: {e}")
                raise

    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Database connection closed")


# Database utility functions for user and session management
async def get_user_by_name(name: str) -> Optional[dict]:
    """Retrieve user from database by name."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    Retrieve user from database by ID.

    Args:
        user_id: The ID of the user to retrieve

    Returns:
        Optional[dict]: User data if found, None otherwise
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    """Retrieve user from database by email"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


async def create_session(user_id: int, session_id: str) -> bool:
    """Create a new session in the database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, user_id) VALUES (%s, %s)", (session_id, user_id)
        )
        connection.commit()
        return True
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


async def get_session(session_id: str) -> Optional[dict]:
    """Retrieve session from database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT *
            FROM sessions s
            WHERE s.id = %s
        """,
            (session_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


async def delete_session(session_id: str) -> bool:
    """Delete a session from the database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        connection.commit()
        return True
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# Method to get all users from the database
async def get_all_users() -> list:
    """Retrieve all users from the database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()  # Return all rows as a list of dictionaries
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# Method to get all sessions from the database
async def get_all_sessions() -> list:
    """Retrieve all sessions from the database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sessions")
        return cursor.fetchall()  # Return all rows as a list of dictionaries
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# Create a new wardrobe item
async def create_wardrobe_item(user_id, item_name, item_description):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO wardrobe (user_id, item_name, item_description)
        VALUES (%s, %s, %s)
    """, (user_id, item_name, item_description))
    connection.commit()
    cursor.close()
    connection.close()

# Get all wardrobe items for a user
async def get_wardrobe_items(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM wardrobe WHERE user_id = %s", (user_id,))
    items = cursor.fetchall()
    cursor.close()
    connection.close()
    return items

# Get a single wardrobe item by ID
async def get_wardrobe_item(item_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM wardrobe WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    cursor.close()
    connection.close()
    return item

async def update_wardrobe_item(item_id, item_name, item_description):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE wardrobe
        SET item_name = %s, item_description = %s
        WHERE id = %s
    """, (item_name, item_description, item_id))
    connection.commit()
    cursor.close()
    connection.close()

# Delete a wardrobe item
async def delete_wardrobe_item(item_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM wardrobe WHERE id = %s", (item_id,))
    connection.commit()
    cursor.close()
    connection.close()


# device registration 

# Add new device to the database
async def add_device(user_id, device_id, device_name):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO devices (user_id, device_id, device_name)
        VALUES (%s, %s, %s);
        """
        cursor.execute(query, (user_id, device_id, device_name))
        connection.commit()

        return device_id
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

async def get_user_devices(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = "SELECT device_id, device_name FROM devices WHERE user_id = %s;"
        cursor.execute(query, (user_id,))
        devices = cursor.fetchall()

        # Convert tuples to dictionaries
        device_list = [{"device_id": device[0], "device_name": device[1]} for device in devices]

        print(device_list)  # Debugging line to ensure correct output
        return device_list
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Delete a device by device_id
async def delete_device_from_db(device_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = "DELETE FROM devices WHERE device_id = %s;"
        cursor.execute(query, (device_id,))
        connection.commit()

        return "Device deleted successfully."
    except Error as e:
        print(f"Error: {e}")
        return "Error deleting device"
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()