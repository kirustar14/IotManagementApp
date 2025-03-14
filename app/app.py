# wardrobe functionality 
import uvicorn
from fastapi import FastAPI, Request, Form, UploadFile, HTTPException, Depends,  Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uuid
import os
from contextlib import asynccontextmanager
from typing import Optional
from mysql.connector import Error
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from datetime import datetime
from fastapi.staticfiles import StaticFiles
import requests
import base64
import httpx
import traceback 

from database import (
    setup_database,
    get_user_by_email,
    get_user_by_id,
    create_session,
    get_session,
    delete_session,
    get_db_connection, 
    get_all_sessions, 
    get_all_users,
    create_wardrobe_item, 
    get_wardrobe_items, 
    get_wardrobe_item, 
    update_wardrobe_item, 
    delete_wardrobe_item,
    get_user_devices,
    delete_device_from_db,
    add_device
)

templates = Jinja2Templates(directory="static")

# Helper function to get the user_id from the session
def get_user_id_from_session(request: Request):
    session_id = request.cookies.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    return session["user_id"]

INIT_USERS = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for managing application startup and shutdown.
    Handles database setup and cleanup in a more structured way.
    """
    # Startup: Setup resources
    try:
        await setup_database(INIT_USERS)  # Make sure setup_database is async
        print("Database setup completed")
        yield
    finally:
        print("Shutdown completed")


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Static file helpers
def read_html(file_path: str) -> str:
    with open(file_path, "r") as f:
        return f.read()


@app.get("/", response_class=HTMLResponse)
async def root():
    return read_html("./static/index.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login if not logged in, or redirect to profile page"""
    session_id = request.cookies.get("sessionId")
    if session_id:
        session = await get_session(session_id)
        if session:
            user = await get_user_by_id(session["user_id"])  
            name = user['name']; 
            if user:
                return RedirectResponse(url=f"/profile/{name}")
    return read_html("./static/login.html")


@app.post("/login")
async def login(request: Request):
    """Validate credentials and create a new session if valid"""
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")

    print(f"Attempting login with email: {email} and password: {password}")
    
    user = await get_user_by_email(email)

    if user:
        print(f"User found: {user}")
    else:
        print("No user found with that email")

    if not user:
        return templates.TemplateResponse("not_found.html", {"request": request, "email": email})
    
    name = user["name"] 
    email = user["email"]
    if user["password"] != password:
            return templates.TemplateResponse("error.html", {"request": request, "email": email}
    )

    user_id = user["id"]
    session_id = str(uuid.uuid4())
    await create_session(user_id, session_id)

    response = RedirectResponse(url=f"/profile/{name}", status_code=303)
    response.set_cookie(key="sessionId", value=session_id, httponly=True)
    return response

@app.post("/logout")
async def logout(request: Request):
    """Clear session and redirect to login page"""
    session_id = request.cookies.get("sessionId")
    if session_id:
        await delete_session(session_id)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("sessionId")
    return response


@app.get("/profile/{name}", response_class=HTMLResponse)
async def user_page(name: str, request: Request):
    """Show user profile if authenticated, error if not"""
    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]

    return templates.TemplateResponse(
        "profile.html", {"request": request, "name": name}
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Show the signup form"""
    return read_html("./static/signup.html")


@app.post("/signup")
async def signup(request: Request):
    """Handle user registration"""
    form_data = await request.form()
    name = form_data.get("name")
    password = form_data.get("password")
    email = form_data.get("email")
    location = form_data.get("location")

    existing_user = await get_user_by_email(email)
    if existing_user:
        return HTMLResponse(content="Email already exists", status_code=400)

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        insert_query = """
            INSERT INTO users (name, password, email, location)
            VALUES (%s, %s, %s, %s) 
        """
        cursor.execute(insert_query, (name, password, email, location))
        connection.commit()
        return RedirectResponse(url="/login", status_code=303)

    except Error as e:
        return HTMLResponse(content=f"An error occurred: {str(e)}", status_code=500)

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# Route to get all users
@app.get("/users", response_class=JSONResponse)
async def get_users():
    """Return details of all users"""
    users = await get_all_users()
    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    return users

# Route to get all sessions
@app.get("/sessions", response_class=JSONResponse)
async def get_sessions():
    """Return details of all sessions"""
    sessions = await get_all_sessions()
    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found")
    return sessions


# Wardrobe functionality

# Route to display the user's wardrobe
@app.get("/wardrobe/{name}", response_class=HTMLResponse)
async def display_wardrobe(name: str, request: Request):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]

    user_id = user_from_session["id"]
    wardrobe_items = await get_wardrobe_items(user_id)

    # Render the wardrobe HTML using Jinja2
    return templates.TemplateResponse("wardrobe.html", {"request": request, "name": name, "wardrobe_items": wardrobe_items})

# Route to show the add item form
@app.get("/wardrobe/add/{name}", response_class=HTMLResponse)
async def add_item_form(name: str, request: Request):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    
    return templates.TemplateResponse("add_item.html", {"request": request, "name": name})

@app.post("/wardrobe/add/{name}", response_class=HTMLResponse)
async def add_item(request: Request, name: str, item_name: str = Form(...), item_description: str = Form(...)):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]

    user_id = user_from_session["id"]
    await create_wardrobe_item(user_id, item_name, item_description)

    # Render the success page
    return templates.TemplateResponse("item_added.html", {"request": request, "name": name})


# Route to handle editing an item in the wardrobe
@app.get("/wardrobe/edit/{name}/{item_id}", response_class=HTMLResponse)
async def edit_item_form(name: str, item_id: int, request: Request):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]
    
    item = await get_wardrobe_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Render the edit page with the item's current data
    return templates.TemplateResponse("edit_item.html", {
        "request": request,
        "name": name,
        "item_id": item_id,
        "item_name": item["item_name"],
        "item_description": item["item_description"]
    })

# Route to handle updating an item in the wardrobe
@app.post("/wardrobe/edit/{name}/{item_id}", response_class=HTMLResponse)
async def update_item(request: Request, name: str, item_id: int, item_name: str = Form(...), item_description: str = Form(...)):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    
    # Update the item in the database
    await update_wardrobe_item(item_id, item_name, item_description)
    
    # Render the success page
    return templates.TemplateResponse("item_updated.html", {"request": request, "name": name})

# Route to handle deleting an item from the wardrobe
@app.post("/wardrobe/delete/{name}/{item_id}", response_class=HTMLResponse)
async def delete_item(request: Request, name: str, item_id: int):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )

    await delete_wardrobe_item(item_id)
    
    # Render the success page
    return templates.TemplateResponse("item_deleted.html", {"request": request, "name": name})



# routes for registering devices 


# Global variable to store the latest device_id (this could be replaced with session management)
latest_device_id = None  # Default value

# Device Registration with user_id
class DeviceRegistration(BaseModel):
    device_name: str  # Only device_name is needed from the form

    @classmethod
    def as_form(
        cls,
        device_name: str = Form(...),  # Only accept device_name in the form
    ):
        return cls(device_name=device_name)
    


@app.get("/register_device/{name}", response_class=HTMLResponse)
async def register_device_form(request: Request, name: str):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )

    # Render the device registration form for the user
    return templates.TemplateResponse("register_device.html", {"request": request, "name": name, "user_id": user_id})


@app.post("/register_device/{name}")
async def register_device(
    request: Request, name: str, device: DeviceRegistration = Depends(DeviceRegistration.as_form)
):
    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )

    device_id = latest_device_id if latest_device_id else str(uuid.uuid4())

    # Check if the device already exists for this user (not across all users)
    devices = await get_user_devices(user_id)
    existing_device = next((d for d in devices if d["device_id"] == device_id), None)
    
    if existing_device:
        message = f"Error: Device '{device.device_name}' with ID '{device_id}' is already registered for this user."
        return templates.TemplateResponse(
            "register_device.html",
            {
                "request": request,
                "name": name,
                "message": message,  # Error message when device is already registered for this user
                "back_to_profile": True  # Flag to show back to profile button
            }
        )
    else:
        # Allow the same device_id for different users
        # Add the device for the current user
        await add_device(user_id, device_id, device.device_name)
        message = "Device registered successfully!"
        return templates.TemplateResponse(
            "register_device.html",
            {
                "request": request,
                "name": name,
                "message": message,  
                "back_to_profile": True 
            }
        ) 
 

@app.get("/view_devices/{name}", response_class=HTMLResponse)
async def view_devices(request: Request, name: str):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]

    devices = await get_user_devices(user_id)

    return templates.TemplateResponse("view_devices.html", {
        "request": request, 
        "name": name,
        "devices": devices
    })


@app.post("/delete_device/{name}/{device_id}")
async def delete_device(request: Request, name: str, device_id: str):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"] 

    # Delete the device by device_id for the user
    result = await delete_device_from_db(device_id)

    if result == "Device deleted successfully.":
        # Fetch the updated list of devices
        devices = await get_user_devices(user_id)

        return templates.TemplateResponse(
            "view_devices.html", 
            {
                "request": request,
                "name": name,
                "devices": devices,
                "success_message": "Device deleted successfully!"  # Pass success message
            }
        )
    else:
        return {"message": "Error deleting device"}


class DeviceRegistration1(BaseModel):
    device_id: str  


# Route to handle the device registration (only device_id and timestamp) sent from mqtt latest device_id is updated
@app.post("/api/register_device1")
async def register_device(device: DeviceRegistration1):
    """Handle device registration data sent from the form or MQTT."""
    
    # Extract the device_id from the incoming request data
    device_id = device.device_id
    
    # Update the latest_device_id to the newly registered device
    global latest_device_id
    latest_device_id = device_id
    
    # Example of returning a success response
    return {"message": "Device id save successful", "device_id": latest_device_id}


# Dasboard + Sensor Data 

app.mount("/static", StaticFiles(directory="static"), name="static")


# Pydantic model for sensor data
class SensorData(BaseModel):
    value: float
    unit: str
    timestamp: str = None
    device_id: str

# Valid sensor types for checking
valid_sensor_types = ["temperature"]

# Function to validate sensor type
def validate_sensor_type(sensor_type: str):
    if sensor_type.lower() not in valid_sensor_types:
        raise HTTPException(status_code=404, detail=f"Sensor type '{sensor_type}' not found")

def fetch_sensor_data(sensor_type, order_by=None, start_date=None, end_date=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = f"SELECT * FROM {sensor_type} WHERE 1=1"
    params = []

    if start_date:
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` >= %s"
            params.append(dt_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format")

    if end_date:
        try:
            dt_end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` <= %s"
            params.append(dt_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format")

    if order_by:
        query += f" ORDER BY {order_by}"
    
    cursor.execute(query, params)
    result = cursor.fetchall()

    cursor.close()
    connection.close()
    
    # Convert the datetime values to string in the expected format.
    for row in result:
        if row.get("timestamp") and isinstance(row["timestamp"], datetime):
            row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    
    return result


@app.get("/dashboard/{name}") 
async def get_dashboard(name: str, request: Request):
    """Show dashboard if authenticated, error if not"""
    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    name = user_from_session["name"]

    return templates.TemplateResponse("dashboard.html", {"request": request, "name": name})

@app.get("/api/{sensor_type}")
async def get_sensor_data(sensor_type: str, request: Request,
                    order_by: str = Query(None, alias="order-by"),
                    start_date: str = Query(None, alias="start-date"),
                    end_date: str = Query(None, alias="end-date")):
    
    # Validate the sensor type
    validate_sensor_type(sensor_type)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)
    name = user_from_session["name"]
    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    
    # Get all device IDs registered to the user
    cursor.execute("SELECT device_id FROM devices WHERE user_id = %s", (user_id,))
    device_ids = [row["device_id"] for row in cursor.fetchall()]
    
    if not device_ids:
        return []  # No devices registered for the user
    
    query = f"SELECT * FROM {sensor_type} WHERE device_id IN ({', '.join(['%s'] * len(device_ids))})"
    params = device_ids

    if start_date:
        try:
            if len(start_date.strip()) == 10:
                start_date += " 00:00:00"
            dt_start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` >= %s"
            params.append(dt_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format")

    if end_date:
        try:
            if len(end_date.strip()) == 10:
                end_date += " 23:59:59"
            dt_end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` <= %s"
            params.append(dt_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format")

    if order_by:
        query += f" ORDER BY {order_by}"

    cursor.execute(query, params)
    result = cursor.fetchall()

    cursor.close()
    connection.close()

    # Convert datetime values to string format
    for row in result:
        if row.get("timestamp") and isinstance(row["timestamp"], datetime):
            row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")

    return result

@app.post("/api/{sensor_type}")
async def insert_sensor_data(sensor_type: str, sensor_data: SensorData):
        # Validate the sensor type
        validate_sensor_type(sensor_type)

        # Parse timestamp or use current time
        timestamp = datetime.strptime(sensor_data.timestamp, "%Y-%m-%d %H:%M:%S") if sensor_data.timestamp else datetime.now()
        device_id = sensor_data.device_id

        # Insert data into the database
        connection = get_db_connection()
        cursor = connection.cursor()
        query = f"""
            INSERT INTO {sensor_type} (value, unit, timestamp, device_id) 
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (sensor_data.value, sensor_data.unit, timestamp, device_id))
        connection.commit()
        cursor.close()
        connection.close()

        return {"message": "Sensor data inserted successfully"}


@app.get("/api/{sensor_type}/{id}")
def get_sensor_entry(sensor_type: str, id: int, request: Request):
    # Validate the sensor type
    validate_sensor_type(sensor_type)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = %s", (id,))
    result = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    if not result:
        raise HTTPException(status_code=404)
    return result


# get latest temperature reading 
@app.get("/api/latest/{sensor_type}")
async def get_sensor_data(sensor_type: str, request: Request,
                          order_by: str = Query(None, alias="order-by"),
                          start_date: str = Query(None, alias="start-date"),
                          end_date: str = Query(None, alias="end-date")):

    # Validate the sensor type
    validate_sensor_type(sensor_type)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)
    
    query = f"SELECT * FROM {sensor_type} WHERE user_id = %s"
    params = [user_id]

    # Fetch only the latest temperature if the sensor type is "temperature"
    if sensor_type == "temperature":
        query += " ORDER BY timestamp DESC LIMIT 1"

    elif start_date:
        try:
            if len(start_date.strip()) == 10:
                start_date += " 00:00:00"
            dt_start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` >= %s"
            params.append(dt_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format")

    if end_date:
        try:
            if len(end_date.strip()) == 10:
                end_date += " 23:59:59"
            dt_end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            query += " AND `timestamp` <= %s"
            params.append(dt_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format")

    if order_by and sensor_type != "temperature":
        query += f" ORDER BY {order_by}"

    cursor.execute(query, params)
    result = cursor.fetchall()

    cursor.close()
    connection.close()

    # Convert datetime values to string format
    for row in result:
        if row.get("timestamp") and isinstance(row["timestamp"], datetime):
            row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")

    return result[0] if sensor_type == "temperature" and result else result


# API Details
EMAIL = "kmarikumaran@ucsd.edu"
PID = "A17877875"
AI_API_URL = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/complete"
IMAGE_API_URL = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/image"

@app.post("/get-outfit")
async def get_outfit(request: Request):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)

    name = user_from_session["name"]
    if user_from_session["name"] != name:
        return templates.TemplateResponse("error.html", {"request": request, "name": name})

    # Step 4: Fetch wardrobe items for the user
    wardrobe = await get_wardrobe_items(user_id)
    item_names = [item["item_name"] for item in wardrobe]

    # Step 5: Fetch the latest temperature data
    async with httpx.AsyncClient() as client:
        temp_response = await client.get(f"http://localhost:8000/api/latest/temperature", cookies={"sessionId": session_id})

    if temp_response.status_code == 200:
        temp_data = temp_response.json()
        temperature = temp_data.get("value")  # Assuming the temp data has a "value" field
    else:
        temperature = None

    location = user_from_session["location"]

    # Step 6: Create a prompt for AI based on available data
    if temperature is not None:
        prompt = f"Based on the current temperature of {temperature}°C and the wardrobe items: {', '.join(item_names)}, what should I wear today?"
    else:
        prompt = f"Based on the wardrobe items: {', '.join(item_names)}, what should I wear today? If I don't have anything, just suggest something for different weather options."

    headers = {
        "email": EMAIL,
        "pid": PID,
    }

    try:
        # Use the AI API to generate the outfit recommendation
        ai_response = requests.post(AI_API_URL, headers=headers, json={"prompt": prompt})

        if ai_response.status_code == 200:
            data = ai_response.json()
            return {"response": data["result"]["response"]}
        else:
            raise HTTPException(status_code=ai_response.status_code, detail="AI API request failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching AI response: {str(e)}")


@app.post("/get-chat-response")
async def get_chat_response(request: Request):
    data = await request.json()
    user_prompt = data.get("prompt", "")
    # Use the AI API to generate a response
    headers = {
        "email": EMAIL,
        "pid": PID,
    }

    try:
        response = requests.post(AI_API_URL, headers=headers, json={"prompt": user_prompt})
        if response.status_code == 200:
            data = response.json()
            return {"response": data["result"]["response"]}
        else:
            raise HTTPException(status_code=response.status_code, detail="AI API request failed")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching AI response: {str(e)}")

@app.post("/generate-image")
async def generate_image(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    
    headers = {"email": EMAIL, "pid": PID, "Content-Type": "application/json"}
    payload = {"prompt": prompt, "width": 512, "height": 512}
    print(headers)
    print(payload)
    try:
        response = requests.post(IMAGE_API_URL, headers=headers, json=payload)
        if response.status_code == 200:         
            image_data = response.content
            base64_image = base64.b64encode(image_data).decode("utf-8")
            return JSONResponse(content={"image_base64": f"data:image/png;base64,{base64_image}"})
        else:
            raise HTTPException(status_code=response.status_code, detail="Image generation API request failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating image: {str(e)}")
    

# Weather page 

@app.get("/weather/{name}")
async def page(request: Request):

    session_id = request.cookies.get("sessionId")
    if not session_id:
        return RedirectResponse(url="/login")
    
    session = await get_session(session_id)
    if not session:
        return RedirectResponse(url="/login")

    user_id = session["user_id"]
    user_from_session = await get_user_by_id(user_id)
    if not user_from_session:
        return HTMLResponse(content="User not found", status_code=404)
    name = user_from_session["name"]

    if user_from_session["name"] != name:
        return templates.TemplateResponse(
            "error.html", {"request": request, "name": name}
        )
    

    user_id = user_from_session["id"]
    wardrobe_items = await get_wardrobe_items(user_id)

    # Render the wardrobe HTML using Jinja2
    return templates.TemplateResponse("weather.html", {"request": request, "name": name, "wardrobe_items": wardrobe_items})


if __name__ == "__main__":
    uvicorn.run("app:app", host="localhost", port=8000, reload=True)
