import pymongo
from bson.objectid import ObjectId
import datetime
import os
import bcrypt
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Atlas Configuration
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://pius:pius7890@cluster0.kjfmyxe.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
MONGO_DB_NAME = "nexfi"

try:
    client = pymongo.MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=50000,
        connectTimeoutMS=100000,
        maxPoolSize=50
    )
    db = client[MONGO_DB_NAME]
    client.server_info()
    logger.info("✓ Successfully connected to MongoDB")
except Exception as e:
    logger.error(f"✗ Failed to connect to MongoDB: {e}")
    raise

# Collections
users = db['users']
posts = db['posts']
follows = db['follows']
messages = db['messages']

# Create indexes for faster queries
try:
    # First, clean up any users with null usernames
    result = users.delete_many({"username": None})
    if result.deleted_count > 0:
        logger.warning(f"⚠️  Cleaned up {result.deleted_count} users with null usernames")
    
    # Also clean up users with empty usernames
    result = users.delete_many({"username": ""})
    if result.deleted_count > 0:
        logger.warning(f"⚠️  Cleaned up {result.deleted_count} users with empty usernames")
    
    # Drop existing indexes if they exist (to recreate them properly)
    try:
        users.drop_index("username_1")
        logger.info("Dropped old username index")
    except:
        pass
    
    try:
        users.drop_index("email_1")
        logger.info("Dropped old email index")
    except:
        pass
    
    # Now create the indexes
    posts.create_index([("timestamp", -1)])
    posts.create_index([("user_id", 1)])
    users.create_index([("username", 1)], unique=True, sparse=False)
    users.create_index([("email", 1)], unique=True, sparse=False)
    follows.create_index([("follower_id", 1)])
    follows.create_index([("following_id", 1)])
    
    logger.info("✓ Database indexes created successfully")
except Exception as e:
    logger.warning(f"⚠️  Index creation warning: {e}")


def register_user(username, password, date_of_birth, gender, email, profile_pic=None):
    """Register a new user"""
    try:
        logger.info(f"Registering user: {username}")
        
        if users.find_one({"username": username}):
            return False, "Username already exists", None
        if users.find_one({"email": email}):
            return False, "Email already exists", None
        if len(username) < 3:
            return False, "Username must be at least 3 characters", None
        if len(password) < 6:
            return False, "Password must be at least 6 characters", None
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        user_data = {
            "username": username,
            "password": hashed_password.decode('utf-8'),
            "date_of_birth": date_of_birth,
            "gender": gender,
            "email": email,
            "profile_pic": profile_pic if profile_pic else "",
            "created_at": datetime.datetime.now()
        }
        
        result = users.insert_one(user_data)
        user_id = str(result.inserted_id)
        logger.info(f"✓ User registered: {username} (ID: {user_id})")
        
        return True, "User registered successfully", user_id
    except Exception as e:
        logger.error(f"✗ Registration error: {e}", exc_info=True)
        return False, str(e), None


def login_user(username, password):
    """Login user"""
    try:
        user = users.find_one({"$or": [{"username": username}, {"email": username}]})
        
        if not user:
            return None, "Invalid username/email or password"
        
        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.info(f"✓ Login successful: {username}")
            return str(user['_id']), "Login successful"
        else:
            return None, "Invalid username/email or password"
            
    except Exception as e:
        logger.error(f"✗ Login error: {e}")
        return None, str(e)


def create_post(user_id, content, image=None):
    """Create a new post"""
    try:
        if not users.find_one({"_id": ObjectId(user_id)}):
            return False, "Invalid user_id"
        
        if not content and not image:
            return False, "Post must have content or an image"
        
        if content and len(content) > 280:
            return False, "Post content must be 1-280 characters"
        
        post_data = {
            "user_id": ObjectId(user_id),
            "content": content if content else "",
            "image": image if image else "",
            "timestamp": datetime.datetime.now(),
            "likes": 0,
            "comments_count": 0
        }
        
        result = posts.insert_one(post_data)
        logger.info(f"✓ Post created by user {user_id}")
        
        return True, "Post created"
    except Exception as e:
        logger.error(f"✗ Post creation error: {e}")
        return False, str(e)


def get_feed(user_id, limit=50):
    """
    Get global feed - ALL posts from ALL users
    Simple, fast, no filtering
    """
    try:
        logger.info(f"Fetching global feed (limit: {limit})")
        
        # Validate user exists
        user_obj_id = ObjectId(user_id)
        if not users.find_one({"_id": user_obj_id}):
            return [], "Invalid user_id"
        
        # Use aggregation pipeline for best performance
        pipeline = [
            # Sort by timestamp (newest first)
            {"$sort": {"timestamp": -1}},
            # Limit results
            {"$limit": limit},
            # Join with users collection
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            # Unwind user info
            {"$unwind": "$user_info"},
            # Project only needed fields
            {
                "$project": {
                    "post_id": {"$toString": "$_id"},
                    "user_id": {"$toString": "$user_id"},
                    "content": 1,
                    "image": 1,
                    "likes": 1,
                    "comments_count": 1,
                    "timestamp": 1,
                    "username": "$user_info.username",
                    "profile_pic": "$user_info.profile_pic"
                }
            }
        ]
        
        feed_posts = list(posts.aggregate(pipeline))
        
        # Convert timestamp to ISO format
        for post in feed_posts:
            post['timestamp'] = post['timestamp'].isoformat()
            post.pop('_id', None)
            # Ensure profile_pic is string
            if not post.get('profile_pic'):
                post['profile_pic'] = ""
        
        logger.info(f"✓ Returned {len(feed_posts)} posts")
        return feed_posts, None
        
    except Exception as e:
        logger.error(f"✗ Feed error: {e}", exc_info=True)
        return [], str(e)


def follow_user(follower_id, following_username):
    """Follow a user"""
    try:
        following = users.find_one({"username": following_username})
        
        if not following:
            return False, "User not found"
        
        following_id = following['_id']
        
        if str(follower_id) == str(following_id):
            return False, "You cannot follow yourself"
        
        existing = follows.find_one({
            "follower_id": ObjectId(follower_id),
            "following_id": following_id
        })
        
        if existing:
            return False, "Already following this user"
        
        follows.insert_one({
            "follower_id": ObjectId(follower_id),
            "following_id": following_id,
            "created_at": datetime.datetime.now()
        })
        
        logger.info(f"✓ User {follower_id} followed @{following_username}")
        return True, f"Followed @{following_username}"
        
    except Exception as e:
        logger.error(f"✗ Follow error: {e}")
        return False, str(e)


def unfollow_user(follower_id, following_username):
    """Unfollow a user"""
    try:
        following = users.find_one({"username": following_username})
        
        if not following:
            return False, "User not found"
        
        result = follows.delete_one({
            "follower_id": ObjectId(follower_id),
            "following_id": following['_id']
        })
        
        if result.deleted_count > 0:
            logger.info(f"✓ User {follower_id} unfollowed @{following_username}")
            return True, f"Unfollowed @{following_username}"
        else:
            return False, "You are not following this user"
            
    except Exception as e:
        logger.error(f"✗ Unfollow error: {e}")
        return False, str(e)


def like_post(post_id, increment=True):
    """Like or unlike a post"""
    try:
        if increment:
            result = posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$inc": {"likes": 1}}
            )
        else:
            result = posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$inc": {"likes": -1}}
            )
        
        if result.modified_count > 0:
            return True, "Like updated"
        else:
            return False, "Post not found"
            
    except Exception as e:
        logger.error(f"✗ Like error: {e}")
        return False, str(e)


def delete_post(post_id, user_id):
    """Delete a post"""
    try:
        post = posts.find_one({"_id": ObjectId(post_id)})
        
        if not post:
            return False, "Post not found"
        
        if str(post['user_id']) != user_id:
            return False, "You can only delete your own posts"
        
        result = posts.delete_one({"_id": ObjectId(post_id)})
        
        if result.deleted_count > 0:
            logger.info(f"✓ Post {post_id} deleted")
            return True, "Post deleted successfully"
        else:
            return False, "Failed to delete post"
            
    except Exception as e:
        logger.error(f"✗ Delete error: {e}")
        return False, str(e)


def get_user_profile(username):
    """Get user profile information"""
    try:
        user = users.find_one(
            {"username": username},
            {"password": 0}
        )
        
        if not user:
            return None, "User not found"
        
        followers_count = follows.count_documents({"following_id": user['_id']})
        following_count = follows.count_documents({"follower_id": user['_id']})
        posts_count = posts.count_documents({"user_id": user['_id']})
        
        profile = {
            "user_id": str(user['_id']),
            "username": user['username'],
            "email": user['email'],
            "profile_pic": user.get('profile_pic', ''),
            "date_of_birth": user.get('date_of_birth', ''),
            "gender": user.get('gender', ''),
            "followers_count": followers_count,
            "following_count": following_count,
            "posts_count": posts_count,
            "created_at": user.get('created_at', '').isoformat() if user.get('created_at') else ''
        }
        
        return profile, None
        
    except Exception as e:
        logger.error(f"✗ Profile error: {e}")
        return None, str(e)



try:
    messages.create_index([("from_user_id", 1), ("to_user_id", 1), ("timestamp", -1)])
    messages.create_index([("to_user_id", 1), ("read", 1)])
    logger.info("✓ Message indexes created successfully")
except Exception as e:
    logger.warning(f"⚠️  Message index creation warning: {e}")


def send_message(from_user_id, to_user_id, text, image=None):
    """Send a message from one user to another"""
    try:
        # Validate both users exist
        from_user = users.find_one({"_id": ObjectId(from_user_id)})
        to_user = users.find_one({"_id": ObjectId(to_user_id)})
        
        if not from_user:
            return False, "Sender not found", None
        if not to_user:
            return False, "Recipient not found", None
        
        if from_user_id == to_user_id:
            return False, "Cannot send message to yourself", None
        
        message_data = {
            "from_user_id": ObjectId(from_user_id),
            "to_user_id": ObjectId(to_user_id),
            "text": text,
            "image": image if image else "",
            "timestamp": datetime.datetime.now(),
            "read": False
        }
        
        result = messages.insert_one(message_data)
        message_id = str(result.inserted_id)
        
        logger.info(f"✓ Message sent from {from_user_id} to {to_user_id}")
        return True, "Message sent", message_id
        
    except Exception as e:
        logger.error(f"✗ Send message error: {e}", exc_info=True)
        return False, str(e), None


def get_messages(user_id, other_user_id, limit=100):
    """Get messages between two users"""
    try:
        user_obj_id = ObjectId(user_id)
        other_obj_id = ObjectId(other_user_id)
        
        # Validate both users exist
        if not users.find_one({"_id": user_obj_id}):
            return [], "Invalid user_id"
        if not users.find_one({"_id": other_obj_id}):
            return [], "Invalid other_user_id"
        
        # Get messages between the two users
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"from_user_id": user_obj_id, "to_user_id": other_obj_id},
                        {"from_user_id": other_obj_id, "to_user_id": user_obj_id}
                    ]
                }
            },
            {"$sort": {"timestamp": 1}},
            {"$limit": limit},
            {
                "$project": {
                    "id": {"$toString": "$_id"},
                    "text": 1,
                    "image": 1,
                    "timestamp": 1,
                    "read": 1,
                    "sent_by_me": {"$eq": ["$from_user_id", user_obj_id]}
                }
            }
        ]
        
        message_list = list(messages.aggregate(pipeline))
        
        # Convert timestamp to ISO format
        for msg in message_list:
            msg['timestamp'] = msg['timestamp'].isoformat()
            msg.pop('_id', None)
        
        logger.info(f"✓ Loaded {len(message_list)} messages between users")
        return message_list, None
        
    except Exception as e:
        logger.error(f"✗ Get messages error: {e}", exc_info=True)
        return [], str(e)


def get_user_conversations(user_id):
    """Get all conversations for a user with last message preview"""
    try:
        user_obj_id = ObjectId(user_id)
        
        if not users.find_one({"_id": user_obj_id}):
            return [], "Invalid user_id"
        
        # Aggregate to get last message for each conversation
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"from_user_id": user_obj_id},
                        {"to_user_id": user_obj_id}
                    ]
                }
            },
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": {
                        "$cond": [
                            {"$eq": ["$from_user_id", user_obj_id]},
                            "$to_user_id",
                            "$from_user_id"
                        ]
                    },
                    "last_message": {"$first": "$text"},
                    "last_message_time": {"$first": "$timestamp"},
                    "last_message_image": {"$first": "$image"},
                    "last_message_sent_by_me": {"$first": {"$eq": ["$from_user_id", user_obj_id]}},
                    "last_message_read": {"$first": "$read"}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": "$user_info"},
            {
                "$lookup": {
                    "from": "messages",
                    "let": {"other_id": "$_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$from_user_id", "$$other_id"]},
                                        {"$eq": ["$to_user_id", user_obj_id]},
                                        {"$eq": ["$read", False]}
                                    ]
                                }
                            }
                        },
                        {"$count": "count"}
                    ],
                    "as": "unread"
                }
            },
            {
                "$project": {
                    "user_id": {"$toString": "$_id"},
                    "username": "$user_info.username",
                    "profile_pic": "$user_info.profile_pic",
                    "last_message": {
                        "$cond": [
                            {"$eq": ["$last_message", ""]},
                            {"$cond": [{"$ne": ["$last_message_image", ""]}, "📷 Photo", ""]},
                            "$last_message"
                        ]
                    },
                    "last_message_time": 1,
                    "last_message_sent_by_me": 1,
                    "last_message_read": 1,
                    "unread_count": {
                        "$ifNull": [{"$arrayElemAt": ["$unread.count", 0]}, 0]
                    },
                    "online": {"$literal": False}
                }
            },
            {"$sort": {"last_message_time": -1}}
        ]
        
        conversations = list(messages.aggregate(pipeline))
        
        # Convert timestamp to ISO format
        for conv in conversations:
            conv['last_message_time'] = conv['last_message_time'].isoformat()
            conv.pop('_id', None)
            if not conv.get('profile_pic'):
                conv['profile_pic'] = ""
        
        logger.info(f"✓ Loaded {len(conversations)} conversations for user {user_id}")
        return conversations, None
        
    except Exception as e:
        logger.error(f"✗ Get conversations error: {e}", exc_info=True)
        return [], str(e)


def mark_messages_read(user_id, other_user_id):
    """Mark all messages from other_user to user as read"""
    try:
        result = messages.update_many(
            {
                "from_user_id": ObjectId(other_user_id),
                "to_user_id": ObjectId(user_id),
                "read": False
            },
            {"$set": {"read": True}}
        )
        
        logger.info(f"✓ Marked {result.modified_count} messages as read")
        return True, f"{result.modified_count} messages marked as read"
        
    except Exception as e:
        logger.error(f"✗ Mark read error: {e}")
        return False, str(e)


def search_users_by_username(query, limit=20):
    """Search users by username"""
    try:
        # Case-insensitive search
        users_list = list(users.find(
            {"username": {"$regex": query, "$options": "i"}},
            {"password": 0, "email": 0}
        ).limit(limit))
        
        # Format results
        results = []
        for user in users_list:
            results.append({
                "user_id": str(user['_id']),
                "username": user['username'],
                "profile_pic": user.get('profile_pic', '')
            })
        
        logger.info(f"✓ Found {len(results)} users matching '{query}'")
        return results, None
        
    except Exception as e:
        logger.error(f"✗ Search users error: {e}")
        return [], str(e)
