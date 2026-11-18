
import streamlit as st
import os
from dotenv import load_dotenv
from google import genai
import sqlite3
import uuid
from datetime import datetime
# ---------------- GEMINI AI SETUP ----------------

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    client = None
def ask_gemini(question):
    if client is None:
        return "Gemini API key not found. Please check your .env file."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=question
        )
        return response.text

    except Exception as e:
        return f"Error: {e}"

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="CampusConnect AI",
    page_icon="🎓",
    layout="wide"
)

DB_NAME = "campus_tickets.db"


# ---------------- DATABASE ----------------

def connect_db():
    return sqlite3.connect(DB_NAME)

def create_table():
    conn = connect_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            student_name TEXT,
            complaint TEXT,
            category TEXT,
            department TEXT,
            priority TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_ticket(ticket):
    conn = connect_db()
    conn.execute("""
        INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ticket)
    conn.commit()
    conn.close()

def get_tickets():
    conn = connect_db()
    data = conn.execute(
        "SELECT * FROM tickets ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return data

def update_status(ticket_id, status):
    conn = connect_db()
    conn.execute(
        "UPDATE tickets SET status=? WHERE ticket_id=?",
        (status, ticket_id)
    )
    conn.commit()
    conn.close()


# ---------------- COMPLAINT UNDERSTANDING ----------------

def analyse_complaint(message):
    msg = message.lower()

    categories = {
        "WiFi / Internet": {
            "words": ["wifi", "wi-fi", "internet", "network", "router"],
            "department": "IT Support"
        },
        "Electrical": {
            "words": ["fan", "light", "electricity", "power", "switch", "socket"],
            "department": "Electrical Department"
        },
        "Hostel": {
            "words": ["hostel", "room", "bed", "water", "washroom", "bathroom"],
            "department": "Hostel Administration"
        },
        "Mess": {
            "words": ["food", "mess", "meal", "breakfast", "lunch", "dinner"],
            "department": "Mess Management"
        },
        "Library": {
            "words": ["library", "book", "issue book", "return book"],
            "department": "Library Department"
        },
        "Maintenance": {
            "words": ["repair", "broken", "cleaning", "maintenance", "leakage"],
            "department": "Maintenance Department"
        }
    }

    category = "General Complaint"
    department = "Campus Administration"

    for name, details in categories.items():
        if any(word in msg for word in details["words"]):
            category = name
            department = details["department"]
            break

    urgent_words = [
        "urgent", "emergency", "danger", "fire",
        "accident", "unsafe", "serious", "immediately"
    ]

    high_words = [
        "not working", "broken", "unable",
        "problem", "issue", "no water", "no internet"
    ]

    if any(word in msg for word in urgent_words):
        priority = "Emergency"
    elif any(word in msg for word in high_words):
        priority = "High"
    else:
        priority = "Normal"

    return category, department, priority


# ---------------- INITIALIZE ----------------

create_table()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "student_name" not in st.session_state:
    st.session_state.student_name = ""


# ---------------- HEADER ----------------

st.title("🎓 CampusConnect AI")
st.subheader("Your Smart Campus Assistance Agent")

st.write(
    "One Message. Intelligent Action. Faster Resolution."
)

st.divider()

# ---------------- NAVIGATION ----------------

page = st.sidebar.radio(
    "Navigation",
    ["🏠 Student Portal", "🛠️ Admin Dashboard"]
)


# ---------------- STUDENT PORTAL ----------------

if page == "🏠 Student Portal":

    st.header("👨‍🎓 Student Assistance Portal")

    name = st.text_input(
        "Enter your name",
        value=st.session_state.student_name,
        placeholder="Your name"
    )

    if name:
        st.session_state.student_name = name

    st.info(
        "Describe your campus problem below. "
        "I will identify the department and register a ticket."
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input(
        "Describe your campus problem..."
    )

    if user_input:

        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        if user_input.lower().strip() in [
            "hi", "hello", "hey", "help"
        ]:
            reply = (
                "Hello! 👋 Welcome to CampusConnect AI. "
                "I can help with hostel, WiFi, electricity, "
                "mess, library and maintenance complaints. "
                "Please describe your problem."
            )

        else:
            category, department, priority = analyse_complaint(
                user_input
            )

            ticket_id = "CC" + uuid.uuid4().hex[:6].upper()

            created_at = datetime.now().strftime(
                "%d-%m-%Y %I:%M %p"
            )

            save_ticket((
                ticket_id,
                name if name else "Student",
                user_input,
                category,
                department,
                priority,
                "Open",
                created_at
            ))

            reply = f"""
Your complaint has been registered successfully! ✅

**Ticket ID:** {ticket_id}

**Category:** {category}

**Assigned Department:** {department}

**Priority:** {priority}

**Status:** Open

Our campus team can now review your complaint.
Please save your Ticket ID for future tracking.
"""

        st.session_state.messages.append({
            "role": "assistant",
            "content": reply
        })

        st.rerun()

    st.divider()

    st.subheader("🔍 Track Your Complaint")

    search_id = st.text_input(
        "Enter your Ticket ID",
        placeholder="Example: CC123ABC"
    )

    if st.button("Track Ticket"):
        all_tickets = get_tickets()

        result = [
            ticket for ticket in all_tickets
            if ticket[0].lower() == search_id.lower().strip()
        ]

        if result:
            ticket = result[0]
            st.success("Ticket found!")

            col1, col2, col3 = st.columns(3)

            col1.metric("Ticket ID", ticket[0])
            col2.metric("Priority", ticket[5])
            col3.metric("Status", ticket[6])

            st.write("**Complaint:**", ticket[2])
            st.write("**Department:**", ticket[4])
        else:
            st.error("Ticket not found. Please check your ID.")


# ---------------- ADMIN DASHBOARD ----------------

elif page == "🛠️ Admin Dashboard":

    st.header("🛠️ Campus Administration Dashboard")

    tickets = get_tickets()

    total = len(tickets)
    open_count = sum(t[6] == "Open" for t in tickets)
    progress_count = sum(
        t[6] == "In Progress" for t in tickets
    )
    resolved_count = sum(
        t[6] == "Resolved" for t in tickets
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Complaints", total)
    c2.metric("Open", open_count)
    c3.metric("In Progress", progress_count)
    c4.metric("Resolved", resolved_count)

    st.divider()

    st.subheader("📋 All Student Complaints")

    if tickets:
        for ticket in tickets:
            with st.expander(
                f"{ticket[0]} | {ticket[2][:55]}"
            ):
                st.write("**Student:**", ticket[1])
                st.write("**Complaint:**", ticket[2])
                st.write("**Category:**", ticket[3])
                st.write("**Department:**", ticket[4])
                st.write("**Priority:**", ticket[5])
                st.write("**Current Status:**", ticket[6])
                st.write("**Date:**", ticket[7])

                new_status = st.selectbox(
                    "Update Complaint Status",
                    ["Open", "In Progress", "Resolved"],
                    index=[
                        "Open", "In Progress", "Resolved"
                    ].index(ticket[6]),
                    key="status_" + ticket[0]
                )

                if st.button(
                    "Save Status",
                    key="save_" + ticket[0]
                ):
                    update_status(ticket[0], new_status)
                    st.success("Status updated successfully!")
                    st.rerun()

    else:
        st.info(
            "No complaints registered yet. "
            "Submit a test complaint through the Student Portal."
        )

    st.divider()

    if st.button("🔄 Refresh Dashboard"):
        st.rerun()


# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "CampusConnect AI | Smart Campus Assistance System"
)
