# seed_playlists.py
from mongodb_helper import MongoDBHelper

db = MongoDBHelper()
db.select_db("SkillSyncDB", "playlists")

demo_playlists = [
    {
        "title": "JavaScript Full Course - Hitesh Choudhary",
        "url": "https://www.youtube.com/playlist?list=PLRAV69dS1uWRX9uEfbd5x1pS14Ck3ab9l",
        "language": "Hindi",
        "rating": 4.9,
        "creator": "Hitesh Choudhary"
    },
    {
        "title": "React.js for Beginners - Chai aur Code",
        "url": "https://www.youtube.com/playlist?list=PLRAV69dS1uWSxP6FPzZ8t4Y_MYEQZ5r3x",
        "language": "Hindi",
        "rating": 4.8,
        "creator": "Chai aur Code"
    },
    {
        "title": "Data Structures & Algorithms - Love Babbar",
        "url": "https://www.youtube.com/playlist?list=PLDzeHZWIZsTryvtXdMr6rPh4IDexB5NIA",
        "language": "Hindi",
        "rating": 4.9,
        "creator": "Love Babbar"
    },
    {
        "title": "Python Roadmap - Code with Harry",
        "url": "https://www.youtube.com/playlist?list=PLu0W_9lII9agICnT8t4iYVSZ3eykIAOME",
        "language": "Hindi",
        "rating": 4.7,
        "creator": "Code with Harry"
    }
]

db.collection.insert_many(demo_playlists)
print("✅ Demo playlists inserted successfully!")
