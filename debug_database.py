import sqlite3
import os

# Database path
DB_PATH = os.environ.get('DB_PATH', 'nexfi.db')

def diagnose_database():
    """Diagnose database issues"""
    print(f"🔍 Diagnosing database: {DB_PATH}\n")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Check users
        print("=" * 60)
        print("👥 USERS TABLE")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        print(f"Total users: {user_count}")
        
        if user_count > 0:
            cursor.execute("SELECT id, username, email FROM users LIMIT 5")
            print("\nFirst 5 users:")
            for user in cursor.fetchall():
                print(f"  ID: {user['id']}, Username: {user['username']}, Email: {user['email']}")
        
        # 2. Check posts
        print("\n" + "=" * 60)
        print("📝 POSTS TABLE")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) as count FROM posts")
        post_count = cursor.fetchone()['count']
        print(f"Total posts: {post_count}")
        
        if post_count > 0:
            cursor.execute("""
                SELECT id, user_id, content, timestamp 
                FROM posts 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            print("\nLast 5 posts:")
            for post in cursor.fetchall():
                print(f"  Post ID: {post['id']}")
                print(f"  User ID: {post['user_id']}")
                print(f"  Content: {post['content'][:50]}...")
                print(f"  Timestamp: {post['timestamp']}")
                print()
        
        # 3. Check if posts have valid user_ids
        print("=" * 60)
        print("🔗 CHECKING POST-USER RELATIONSHIPS")
        print("=" * 60)
        cursor.execute("""
            SELECT 
                p.id as post_id,
                p.user_id,
                u.id as valid_user_id,
                u.username
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            LIMIT 10
        """)
        
        posts_with_users = cursor.fetchall()
        orphaned_posts = 0
        valid_posts = 0
        
        for row in posts_with_users:
            if row['valid_user_id'] is None:
                orphaned_posts += 1
                print(f"  ⚠️  Post {row['post_id']} has invalid user_id: {row['user_id']}")
            else:
                valid_posts += 1
                print(f"  ✅ Post {row['post_id']} → User {row['username']} (ID: {row['valid_user_id']})")
        
        print(f"\n✅ Valid posts: {valid_posts}")
        print(f"⚠️  Orphaned posts (no matching user): {orphaned_posts}")
        
        # 4. Test the exact query used in get_feed
        print("\n" + "=" * 60)
        print("🧪 TESTING GET_FEED QUERY")
        print("=" * 60)
        cursor.execute('''
            SELECT 
                p.id as post_id,
                p.user_id,
                p.content,
                p.image,
                p.likes,
                p.comments_count,
                p.timestamp,
                u.username,
                u.profile_pic
            FROM posts p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.timestamp DESC
            LIMIT 20
        ''')
        
        feed_posts = cursor.fetchall()
        print(f"Query returned: {len(feed_posts)} posts")
        
        if len(feed_posts) > 0:
            print("\nFirst post from query:")
            first_post = feed_posts[0]
            for key in first_post.keys():
                print(f"  {key}: {first_post[key]}")
        else:
            print("❌ Query returned 0 posts!")
            print("\nThis means the JOIN is failing.")
            print("Checking data types...")
            
            # Check data types
            cursor.execute("SELECT user_id FROM posts LIMIT 1")
            post_user_id = cursor.fetchone()
            if post_user_id:
                print(f"  Post user_id type: {type(post_user_id['user_id'])}")
                print(f"  Post user_id value: {post_user_id['user_id']}")
            
            cursor.execute("SELECT id FROM users LIMIT 1")
            user_id = cursor.fetchone()
            if user_id:
                print(f"  User id type: {type(user_id['id'])}")
                print(f"  User id value: {user_id['id']}")
        
        # 5. Check follows
        print("\n" + "=" * 60)
        print("👥 FOLLOWS TABLE")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) as count FROM follows")
        follow_count = cursor.fetchone()['count']
        print(f"Total follows: {follow_count}")
        
        # 6. Check messages
        print("\n" + "=" * 60)
        print("💬 MESSAGES TABLE")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        message_count = cursor.fetchone()['count']
        print(f"Total messages: {message_count}")
        
        # 7. Summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"Users: {user_count}")
        print(f"Posts: {post_count}")
        print(f"Valid posts with users: {valid_posts}")
        print(f"Orphaned posts: {orphaned_posts}")
        print(f"Follows: {follow_count}")
        print(f"Messages: {message_count}")
        
        if post_count > 0 and len(feed_posts) == 0:
            print("\n❌ PROBLEM DETECTED:")
            print("Posts exist but feed query returns 0 results.")
            print("This is likely a JOIN issue - posts.user_id doesn't match users.id")
            print("\n💡 SOLUTIONS:")
            print("1. Run fix_orphaned_posts() to fix existing posts")
            print("2. Or recreate database with correct data types")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def fix_orphaned_posts():
    """Fix posts with invalid user_ids"""
    print("\n🔧 Attempting to fix orphaned posts...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Find orphaned posts
        cursor.execute("""
            SELECT p.id, p.user_id
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE u.id IS NULL
        """)
        
        orphaned = cursor.fetchall()
        
        if not orphaned:
            print("✅ No orphaned posts found!")
            return
        
        print(f"Found {len(orphaned)} orphaned posts")
        
        # Get the first valid user
        cursor.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        first_user = cursor.fetchone()
        
        if not first_user:
            print("❌ No users found in database!")
            return
        
        first_user_id = first_user[0]
        print(f"Assigning orphaned posts to user ID: {first_user_id}")
        
        # Update orphaned posts
        for post_id, old_user_id in orphaned:
            cursor.execute("""
                UPDATE posts 
                SET user_id = ? 
                WHERE id = ?
            """, (first_user_id, post_id))
            print(f"  Fixed post {post_id}: {old_user_id} → {first_user_id}")
        
        conn.commit()
        print(f"✅ Fixed {len(orphaned)} posts")
        
    except Exception as e:
        print(f"❌ Error fixing posts: {e}")
        conn.rollback()
    finally:
        conn.close()


def recreate_database():
    """Recreate database with fresh schema"""
    print("\n⚠️  WARNING: This will DELETE all data!")
    confirm = input("Type 'YES' to recreate database: ")
    
    if confirm != "YES":
        print("Cancelled.")
        return
    
    print("\n🗑️  Deleting old database...")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"✅ Deleted {DB_PATH}")
    
    print("\n📦 Creating new database...")
    import db
    db.init_database()
    print("✅ New database created!")


if __name__ == "__main__":
    print("🔍 NexFi Database Diagnostic Tool\n")
    
    while True:
        print("\nOptions:")
        print("1. Diagnose database")
        print("2. Fix orphaned posts")
        print("3. Recreate database (deletes all data)")
        print("4. Exit")
        
        choice = input("\nChoice (1-4): ").strip()
        
        if choice == "1":
            diagnose_database()
        elif choice == "2":
            fix_orphaned_posts()
            print("\nRun option 1 to verify the fix.")
        elif choice == "3":
            recreate_database()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")