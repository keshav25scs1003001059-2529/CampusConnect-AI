
import streamlit as st
import os
import sqlite3
import uuid
import csv
import io
import hmac
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()

st.set_page_config(
    page_title="CampusConnect AI",
    page_icon="🎓",
    layout="wide"
)

def get_secret(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None

GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        client = None

DB_NAME = "campus_tickets.db"


def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    conn = connect_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            student_name TEXT NOT NULL,
            complaint TEXT NOT NULL,
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
        INSERT INTO tickets
        (ticket_id, student_name, complaint, category,
         department, priority, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket["ticket_id"],
        ticket["student_name"],
        ticket["complaint"],
        ticket["category"],
        ticket["department"],
        ticket["priority"],
        ticket["status"],
        ticket["created_at"]
    ))
    conn.commit()
    conn.close()


def get_all_tickets():
    conn = connect_db()
    rows = conn.execute(
        "SELECT * FROM tickets ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_ticket(ticket_id):
    conn = connect_db()
    row = conn.execute(
        "SELECT * FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    ).fetchone()
    conn.close()
    return row


def update_status(ticket_id, status):
    conn = connect_db()
    conn.execute(
        "UPDATE tickets SET status = ? WHERE ticket_id = ?",
        (status, ticket_id)
    )
    conn.commit()
    conn.close()


def analyse_complaint(complaint):
    text = complaint.lower()

    categories = {
        "WiFi / Internet": (
            ["wifi", "internet", "network", "connection"],
            "IT Department"
        ),
        "Electrical": (
            ["electricity", "light", "fan", "power", "electric"],
            "Electrical Department"
        ),
        "Hostel": (
            ["hostel", "room", "warden", "bed", "water"],
            "Hostel Administration"
        ),
        "Mess": (
            ["food", "mess", "meal", "canteen"],
            "Mess Department"
        ),
        "Library": (
            ["library", "book", "reading"],
            "Library Department"
        ),
        "Maintenance": (
            ["cleaning", "repair", "broken", "maintenance"],
            "Maintenance Department"
        )
    }

    category = "General"
    department = "Student Support Department"

    for cat, (keywords, dept) in categories.items():
        if any(word in text for word in keywords):
            category = cat
            department = dept
            break

    if any(word in text for word in ["emergency", "danger", "fire", "accident"]):
        priority = "Emergency"
    elif any(word in text for word in ["urgent", "immediately", "serious"]):
        priority = "High"
    else:
        priority = "Normal"

    return category, department, priority



def ask_gemini(question):
    if not client:
        return (
            "The AI assistant is not configured yet. "
            "Please add your Gemini API key in the app secrets."
        )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=(
                "You are CampusConnect AI, a helpful assistant "
                "for the CampusConnect AI student support platform. "
                "Answer clearly and politely in simple language.\n\n"

                "YOUR FEATURES:\n"
                "1. Student Portal: Students can submit complaints.\n"
                "2. Complaint Tracking: Students can track complaints "
                "using their Ticket ID.\n"
                "3. AI Assistance: Help students with campus problems.\n\n"

                "INSTRUCTIONS:\n"
                "- Give helpful solutions to student problems.\n"
                "- Recommend Student Portal → Submit Complaint "
                "when students report campus issues.\n"
                "- Explain that students can track complaints "
                "using their Ticket ID.\n"
                "- Never claim that you submitted a complaint.\n"
                "- Never invent official college policies, contacts "
                "or timetables.\n"
                "- Keep answers friendly and concise.\n\n"

                + question
            )
        )

        return response.text or "I could not generate a response."

    except Exception as e:
        return f"Gemini Error: {str(e)}"


create_table()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False


st.sidebar.title("🎓 CampusConnect AI")
st.sidebar.caption("Your Smart Campus Assistant")

page = st.sidebar.radio(
    "Navigate",
    ["Student Portal", "AI Assistant", "Admin Dashboard"]
)

st.sidebar.divider()
st.sidebar.info("Helping students connect with campus support.")


if page == "Student Portal":
    st.title("🎓 Student Support Portal")
    st.write("Submit a complaint and track its progress.")

    with st.form("complaint_form"):
        student_name = st.text_input("Your full name")
        complaint = st.text_area(
            "Describe your complaint",
            placeholder="Example: WiFi is not working in my hostel room."
        )
        submitted = st.form_submit_button(
            "Submit Complaint",
            use_container_width=True
        )

    if submitted:
        if not student_name.strip() or not complaint.strip():
            st.error("Please enter your name and complaint.")
        else:
            category, department, priority = analyse_complaint(complaint)

            ticket_id = "CC-" + uuid.uuid4().hex[:6].upper()

            ticket = {
                "ticket_id": ticket_id,
                "student_name": student_name.strip(),
                "complaint": complaint.strip(),
                "category": category,
                "department": department,
                "priority": priority,
                "status": "Open",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            save_ticket(ticket)

            st.success("Your complaint has been submitted!")
            st.subheader("Your Ticket Details")
            st.code(ticket_id)

            col1, col2, col3 = st.columns(3)
            col1.metric("Category", category)
            col2.metric("Priority", priority)
            col3.metric("Status", "Open")

            st.info(f"Assigned department: {department}")
            st.warning("Save your ticket ID to track your complaint.")


    st.divider()
    st.subheader("🔍 Track Your Complaint")

    search_id = st.text_input("Enter your ticket ID")

    if st.button("Track Ticket"):
        if not search_id.strip():
            st.warning("Please enter a ticket ID.")
        else:
            ticket = get_ticket(search_id.strip().upper())

            if ticket:
                st.success("Ticket found!")
                st.write("**Student:**", ticket["student_name"])
                st.write("**Complaint:**", ticket["complaint"])
                st.write("**Category:**", ticket["category"])
                st.write("**Department:**", ticket["department"])
                st.write("**Priority:**", ticket["priority"])
                st.write("**Status:**", ticket["status"])
                st.write("**Submitted:**", ticket["created_at"])
            else:
                st.error("Ticket not found. Please check the ID.")


elif page == "AI Assistant":
    st.title("🤖 CampusConnect AI Assistant")
    st.write("Ask questions and get help with campus-related queries.")

    if not client:
        st.warning(
            "Gemini API key is not configured. "
            "Add GEMINI_API_KEY in your app secrets to enable AI chat."
        )

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask your campus assistant...")

    if prompt:
        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        answer = ask_gemini(prompt)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer
        })

        with st.chat_message("assistant"):
            st.markdown(answer)

    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()


elif page == "Admin Dashboard":
    st.title("🔐 Admin Dashboard")

    if not ADMIN_PASSWORD:
        st.error(
            "Admin login is disabled. Configure ADMIN_PASSWORD "
            "in Streamlit Cloud Secrets."
        )

    elif not st.session_state.admin_logged_in:
        password = st.text_input("Admin Password", type="password")

        if st.button("Login"):
            if hmac.compare_digest(password, ADMIN_PASSWORD):
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    else:
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

        tickets = get_all_tickets()

        total = len(tickets)
        open_count = sum(t["status"] == "Open" for t in tickets)
        progress_count = sum(
            t["status"] == "In Progress" for t in tickets
        )
        resolved_count = sum(
            t["status"] == "Resolved" for t in tickets
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Complaints", total)
        col2.metric("Open", open_count)
        col3.metric("In Progress", progress_count)
        col4.metric("Resolved", resolved_count)

        st.divider()
        st.subheader("All Student Complaints")

        filter_status = st.selectbox(
            "Filter by status",
            ["All", "Open", "In Progress", "Resolved"]
        )

        filtered_tickets = [
            t for t in tickets
            if filter_status == "All" or t["status"] == filter_status
        ]

        if not filtered_tickets:
            st.info("No complaints found.")
        else:
            for ticket in filtered_tickets:
                with st.expander(
                    f'{ticket["ticket_id"]} | {ticket["category"]} | {ticket["status"]}'
                ):
                    st.write("**Student:**", ticket["student_name"])
                    st.write("**Complaint:**", ticket["complaint"])
                    st.write("**Department:**", ticket["department"])
                    st.write("**Priority:**", ticket["priority"])
                    st.write("**Created:**", ticket["created_at"])

                    new_status = st.selectbox(
                        "Update Status",
                        ["Open", "In Progress", "Resolved"],
                        index=[
                            "Open", "In Progress", "Resolved"
                        ].index(ticket["status"]),
                        key=f'status_{ticket["ticket_id"]}'
                    )

                    if st.button(
                        "Save Status",
                        key=f'save_{ticket["ticket_id"]}'
                    ):
                        update_status(ticket["ticket_id"], new_status)
                        st.success("Status updated.")
                        st.rerun()

        if tickets:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Ticket ID", "Student", "Complaint", "Category",
                "Department", "Priority", "Status", "Created At"
            ])

            for t in tickets:
                writer.writerow([
                    t["ticket_id"],
                    t["student_name"],
                    t["complaint"],
                    t["category"],
                    t["department"],
                    t["priority"],
                    t["status"],
                    t["created_at"]
                ])

            st.download_button(
                "Download Complaints CSV",
                output.getvalue(),
                file_name="campus_complaints.csv",
                mime="text/csv"
            )


st.sidebar.divider()
st.sidebar.caption("CampusConnect AI | Student Support Platform")
