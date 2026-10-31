
# ==========================================
# STUDENT MANAGEMENT SYSTEM
# Dummy code for security scanner testing
# ==========================================

import datetime
import random


# ------------------------------------------
# 1. APPLICATION CONFIGURATION
# ------------------------------------------

APP_NAME = "Student Management System"
VERSION = "2.1.0"
DEBUG_MODE = True

# SENSITIVE: Hardcoded password
password = "DemoPassword123"

# SENSITIVE: Fake API key for testing
api_key = "AIzaSyDemoFakeKey123456789"

# NON-SENSITIVE
MAX_STUDENTS = 100
DEFAULT_DEPARTMENT = "Computer Engineering"


# ------------------------------------------
# 2. STUDENT INFORMATION
# ------------------------------------------

students = [
    {
        "id": 101,
        "name": "Rahul Sharma",
        "email": "rahul.sharma@example.com",
        "phone": "9876543210",
        "department": "Computer Engineering",
        "marks": 85
    },
    {
        "id": 102,
        "name": "Priya Naik",
        "email": "priya.naik@example.com",
        "phone": "9123456780",
        "department": "Information Technology",
        "marks": 92
    },
    {
        "id": 103,
        "name": "Aarav Patil",
        "email": "aarav.patil@example.com",
        "phone": "9988776655",
        "department": "Electronics",
        "marks": 78
    }
]


# ------------------------------------------
# 3. DATABASE SETTINGS
# ------------------------------------------

DATABASE_NAME = "student_database"
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432

# SENSITIVE: Fake database password
db_password = "FakeDatabasePass456"


# ------------------------------------------
# 4. STUDENT FUNCTIONS
# ------------------------------------------

def calculate_average(marks):

    if len(marks) == 0:
        return 0

    return sum(marks) / len(marks)


def display_students():

    print("\nSTUDENT DETAILS")

    for student in students:

        print("ID:", student["id"])
        print("Name:", student["name"])
        print("Department:", student["department"])
        print("Marks:", student["marks"])
        print("------------------------")


def find_student(student_id):

    for student in students:

        if student["id"] == student_id:
            return student

    return None


# ------------------------------------------
# 5. USER ACCOUNT INFORMATION
# ------------------------------------------

user_accounts = [
    {
        "username": "rahul123",
        "email": "rahul123@example.com",
        "password": "RahulDemo789"
    },
    {
        "username": "priya456",
        "email": "priya456@example.com",
        "password": "PriyaDemo456"
    }
]


# ------------------------------------------
# 6. CONTACT INFORMATION
# ------------------------------------------

ADMIN_NAME = "System Administrator"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PHONE = "9876501234"

SUPPORT_EMAIL = "support@example.com"


# ------------------------------------------
# 7. REPORT GENERATION
# ------------------------------------------

def generate_report():

    total_students = len(students)

    marks = [
        student["marks"]
        for student in students
    ]

    average = calculate_average(marks)

    print("\nSTUDENT REPORT")
    print("Application:", APP_NAME)
    print("Total students:", total_students)
    print("Average marks:", average)
    print("Generated on:", datetime.datetime.now())


# ------------------------------------------
# 8. NORMAL NON-SENSITIVE OPERATIONS
# ------------------------------------------

def greet_user(name):

    print("Welcome", name)
    print("Thank you for using", APP_NAME)


def generate_student_id():

    return random.randint(1000, 9999)


def check_result(marks):

    if marks >= 40:
        return "PASS"

    return "FAIL"


# ------------------------------------------
# 9. MAIN PROGRAM
# ------------------------------------------

if __name__ == "__main__":

    greet_user("Guest")

    display_students()

    generate_report()

    print("\nStudent with ID 101:")
    print(find_student(101))

    print("\nGenerated ID:")
    print(generate_student_id())

    print("\nApplication running successfully.")
