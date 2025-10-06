"""
Database Cleanup Script
Run this to fix duplicate/null username issues
"""

import pymongo
from bson.objectid import ObjectId
import os

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://marlon:Mongo2604@cluster0.8m2lu.mongodb.net/nup?retryWrites=true&w=majority")
MONGO_DB_NAME = "nup"

print("🔧 Connecting to MongoDB...")
client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

users = db['users']
posts = db['posts']
follows = db['follows']

print("✓ Connected to MongoDB\n")

# Step 1: Find users with null or empty usernames
print("📊 Analyzing database...")
null_users = list(users.find({"username": None}))
empty_users = list(users.find({"username": ""}))

print(f"Found {len(null_users)} users with NULL username")
print(f"Found {len(empty_users)} users with EMPTY username\n")

# Step 2: Show what will be deleted
if null_users or empty_users:
    print("⚠️  The following users will be DELETED:\n")
    
    for user in null_users + empty_users:
        print(f"  - ID: {user['_id']}")
        print(f"    Email: {user.get('email', 'N/A')}")
        print(f"    Created: {user.get('created_at', 'N/A')}")
        print()
    
    response = input("Do you want to DELETE these users? (yes/no): ")
    
    if response.lower() == 'yes':
        # Delete users with null username
        result1 = users.delete_many({"username": None})
        print(f"✓ Deleted {result1.deleted_count} users with NULL username")
        
        # Delete users with empty username
        result2 = users.delete_many({"username": ""})
        print(f"✓ Deleted {result2.deleted_count} users with EMPTY username")
        
        # Clean up orphaned posts from deleted users
        deleted_user_ids = [u['_id'] for u in null_users + empty_users]
        result3 = posts.delete_many({"user_id": {"$in": deleted_user_ids}})
        print(f"✓ Deleted {result3.deleted_count} orphaned posts")
        
        # Clean up orphaned follows
        result4 = follows.delete_many({
            "$or": [
                {"follower_id": {"$in": deleted_user_ids}},
                {"following_id": {"$in": deleted_user_ids}}
            ]
        })
        print(f"✓ Deleted {result4.deleted_count} orphaned follow relationships")
    else:
        print("❌ Cleanup cancelled")
        exit()
else:
    print("✓ No problematic users found!")

# Step 3: Drop and recreate indexes
print("\n🔨 Rebuilding indexes...")

try:
    # Drop old indexes
    try:
        users.drop_index("username_1")
        print("✓ Dropped old username index")
    except Exception as e:
        print(f"  (username index didn't exist: {e})")
    
    try:
        users.drop_index("email_1")
        print("✓ Dropped old email index")
    except Exception as e:
        print(f"  (email index didn't exist: {e})")
    
    # Create new indexes
    users.create_index([("username", 1)], unique=True)
    print("✓ Created username index")
    
    users.create_index([("email", 1)], unique=True)
    print("✓ Created email index")
    
    posts.create_index([("timestamp", -1)])
    print("✓ Created timestamp index")
    
    posts.create_index([("user_id", 1)])
    print("✓ Created user_id index")
    
    follows.create_index([("follower_id", 1)])
    follows.create_index([("following_id", 1)])
    print("✓ Created follow indexes")
    
except Exception as e:
    print(f"❌ Error creating indexes: {e}")

# Step 4: Verify database state
print("\n📊 Final Database State:")
total_users = users.count_documents({})
total_posts = posts.count_documents({})
total_follows = follows.count_documents({})

print(f"  Users: {total_users}")
print(f"  Posts: {total_posts}")
print(f"  Follows: {total_follows}")

# Check for any remaining issues
remaining_null = users.count_documents({"username": None})
remaining_empty = users.count_documents({"username": ""})

if remaining_null > 0 or remaining_empty > 0:
    print(f"\n⚠️  WARNING: Still have {remaining_null + remaining_empty} problematic users!")
else:
    print(f"\n✅ Database is clean and ready!")

print("\n🎉 Cleanup complete!")
client.close()