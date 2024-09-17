import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("./firebase-admin-sdk.json")
firebase_admin.initialize_app(
    cred, 
    {
    'storageBucket': 'image-recognition-2a553.appspot.com'
    }
)

db = firestore.client()
