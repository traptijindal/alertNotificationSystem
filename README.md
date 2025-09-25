#  Alerting & Notification Platform (MVP)

##  Overview
This project implements a **backend system for alerts and notifications** using **FastAPI**.  

The system supports:  
- **Admins**: Configure alerts, set visibility (organization, team, or user), and ensure recurring reminders every 2 hours.  
- **End Users**: Receive alerts relevant to them, snooze alerts for the day, and manage their read/unread status.  

It demonstrates **state management (read/unread/snoozed)**, **delivery strategies**, **reminders**, and **analytics**.  

---

##  Features

###  Admin Features
- Create, update, and list alerts (`/admin/alerts`)  
- Define alert visibility:
  - **Organization** → visible to all users  
  - **Team** → visible only to users of a team  
  - **User** → visible only to selected users  
- Recurring reminders every 2 hours until user snoozes the alert  
- View delivery logs (`/admin/deliveries`)  

### End User Features
- Fetch alerts relevant to the user (`/users/{user_id}/alerts`)  
- Mark alerts as **read** or **unread**  
- Snooze alerts until the end of the day  

### Analytics
- `/analytics` endpoint shows:
  - Delivered vs Read alerts  
  - Snoozed counts per alert  
  - Alerts breakdown by severity  

---

## Tech Stack
- **Backend Framework**: FastAPI  
- **Language**: Python 3.9+  
- **Data Store**: In-memory (Python dicts) for demo purposes  
- **Run Server**: Uvicorn  

---

##  Setup & Run

1. **Install dependencies**
   ```bash
   pip install fastapi uvicorn pydantic
2. **Run the server**
   ```bash
   python alertNotification.py
3. **Interactive API Docs**
   ```bash
   (http://127.0.0.1:8000/docs)

##  Example Endpoints

###  Admin
- **Create Alert**
  ```http
  POST /admin/alerts
- **List Alerts**
  ```GET /admin/alerts
- **Trigger Reminders**
  ```POST /system/trigger_reminders
### User
- **List Alerts for a User**
  ```GET /users/{user_id}/alerts
- **Snooze Alert**
  ```POST /users/{user_id}/alerts/{alert_id}/snooze
- **Mark Read**
   ```POST /users/{user_id}/alerts/{alert_id}/read
- **Mark Unread**
  ```POST /users/{user_id}/alerts/{alert_id}/unread
### Analytics
- **View Metrics**
   ```GET /analytics
## Demo Data (Seeded)

When the server starts, it automatically seeds demo data:

- **Teams**:  
  - Engineering  
  - Marketing  

- **Users**:  
  - Alice  
  - Bob  
  - Carol  

- **Sample Alerts**:  
  - *System Maintenance* (Org-wide)  
  - *Engineering Standup Postponed* (Team-specific)  
  - *Security Incident* (User-specific for Alice)  

---

## Screenshots
<img width="580" height="166" alt="image" src="https://github.com/user-attachments/assets/465ea789-d129-4772-af32-0747d5328d07" />
<img width="641" height="466" alt="image" src="https://github.com/user-attachments/assets/914aba85-ca25-4cf6-ba07-1fc69804c7cd" />
<img width="1066" height="671" alt="image" src="https://github.com/user-attachments/assets/204cb1f1-67e2-4f26-91f5-177de1443622" />
<img width="542" height="504" alt="image" src="https://github.com/user-attachments/assets/c78140ab-79a0-437a-b600-c6ff8338d402" />
<img width="783" height="599" alt="image" src="https://github.com/user-attachments/assets/a5a7ef78-2c5d-46b1-9728-57772cc64551" />



