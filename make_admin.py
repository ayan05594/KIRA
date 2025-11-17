#!/usr/bin/env python3
"""
Script to promote a user to admin role
Usage: python3 make_admin.py <email>
"""

import sys
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
try:
    load_dotenv()
except:
    pass

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://kira_user:kira_db_1234@kira.qzitaui.mongodb.net/kira?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true")

def make_admin(email):
    """Promote a user to admin role"""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client['kira']
        
        # Check if user exists
        user = db.users.find_one({"email": email})
        
        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False
        
        # Check if already admin
        if user.get('role') == 'admin':
            print(f"ℹ️  User '{email}' is already an admin")
            return True
        
        # Promote to admin
        result = db.users.update_one(
            {"email": email},
            {"$set": {"role": "admin"}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Success! User '{email}' has been promoted to admin")
            print(f"\nYou can now access the admin dashboard at:")
            print(f"http://localhost:5001/admin")
            return True
        else:
            print(f"❌ Error: Failed to update user role")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        try:
            client.close()
        except:
            pass

def list_users():
    """List all users in the database"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client['kira']
        
        users = db.users.find({}, {"name": 1, "email": 1, "role": 1})
        user_list = list(users)
        
        if not user_list:
            print("No users found in database")
            return
        
        print("\n📋 All Users:")
        print("-" * 80)
        print(f"{'Name':<30} {'Email':<35} {'Role':<10}")
        print("-" * 80)
        
        for user in user_list:
            name = user.get('name', 'N/A')
            email = user.get('email', 'N/A')
            role = user.get('role', 'user')
            print(f"{name:<30} {email:<35} {role:<10}")
        
        print("-" * 80)
        print(f"Total: {len(user_list)} users\n")
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    print("🔐 KiRA Admin Promotion Tool")
    print("=" * 80)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python3 make_admin.py <email>          - Promote user to admin")
        print("  python3 make_admin.py --list           - List all users")
        print("\nExample:")
        print("  python3 make_admin.py user@kiit.ac.in")
        print()
        list_users()
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_users()
    else:
        email = sys.argv[1]
        make_admin(email)

