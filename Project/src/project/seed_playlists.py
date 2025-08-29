from mongodb_helper import MongoDBHelper

# connect
db = MongoDBHelper()
db.select_db("SkillSyncDB", "playlists")

# sample playlists
sample_playlists = [
    {"title": "Python Basics (English)", "language": "English", "rating": 4.8,
     "url": "https://youtube.com/playlist?list=PLPythonBasics"},
    {"title": "DSA in Hindi", "language": "Hindi", "rating": 4.7,
     "url": "https://youtube.com/playlist?list=PLDSAHindi"},
    {"title": "Machine Learning Crash Course", "language": "English", "rating": 4.9,
     "url": "https://youtube.com/playlist?list=PLMLCrash"}
]

# insert into collection
db.collection.insert_many(sample_playlists)
print("✅ Sample playlists inserted")
