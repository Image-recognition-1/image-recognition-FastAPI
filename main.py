import json
from typing import List, Literal, Optional
from fastapi import FastAPI, Query, Request, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
import ssl
import requests
from datetime import datetime

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('./cert.pem', keyfile='./key.pem')

cred = credentials.Certificate('./firebase-admin-sdk.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

app = FastAPI()

origins = [
    "http://localhost:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class LoginRequest(BaseModel):
    email: str
    password: str

class Purchase(BaseModel):
    payment_method: str
    purchase_date: datetime
    token_amount: int
    user_id: str

class Expense(BaseModel):
    expense_date: datetime
    image_id: str
    token_amount: int
    user_id: str

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        api_key = "AIzaSyAXR9sM7XtgKdCeP zfL76Siifoa_UPCstE"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        payload = {
            "email": form_data.username,
            "password": form_data.password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=payload)
        response_data = response.json()
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response_data.get("error", {}).get("message", "Login failed"))
        
        return {"message": "Login successful", "token": response_data["idToken"]}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login failed: {e}")


@app.get("/verify-token")
async def verify_token(request: Request):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing Authorization Header")
        
        token = auth_header.split(" ")[1]

        decoded_token = auth.verify_id_token(token)

        return {"message": "Token is valid", "decoded_token": decoded_token}

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    

@app.post("/add-purchase", dependencies=[Depends(verify_token)])
async def add_purchase(purchase: Purchase):
    user_ref = db.collection('users').document(purchase.user_id)
    try:
        transaction = db.transaction()
        @firestore.transactional
        def update_tokens(transaction, user_ref):
            user_doc = user_ref.get(transaction=transaction)
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="User does not exist")
            new_tokens = user_doc.get('availableTokens') + purchase.token_amount
            transaction.update(user_ref, {'availableTokens': new_tokens})
            transaction.set(db.collection('purchases').document(), purchase.dict())

        update_tokens(transaction, user_ref)
        return {"message": f"Added {purchase.token_amount} tokens to user {purchase.user_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction failed: {e}")

@app.post("/add-expense", dependencies=[Depends(verify_token)])
async def add_expense(expense: Expense):
    user_ref = db.collection('users').document(expense.user_id)
    try:
        transaction = db.transaction()
        @firestore.transactional
        def update_tokens(transaction, user_ref):
            user_doc = user_ref.get(transaction=transaction)
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="User does not exist")
            new_tokens = user_doc.get('availableTokens') - expense.token_amount
            transaction.update(user_ref, {'availableTokens': new_tokens})
            transaction.set(db.collection('expenses').document(), expense.dict())

        update_tokens(transaction, user_ref)
        return {"message": f"Subtracted {expense.token_amount} tokens from user {expense.user_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction failed: {e}")
    
@app.get("/get-expenses")
async def get_expenses(
    user_id: Optional[str] = Query(None, description="The ID of the user"),
    expense_date: Optional[datetime] = Query(None, description="Expenses after this date (ISO 8601 format)")):
    try:
        expenses_ref = db.collection('expenses')

        if user_id and expense_date:
            expenses_query = expenses_ref.where('user_id', '==', user_id).where('expense_date', '>', expense_date).order_by('expense_date', direction=firestore.Query.DESCENDING)
        elif user_id:
            expenses_query = expenses_ref.where('user_id', '==', user_id).order_by('expense_date', direction=firestore.Query.DESCENDING)
        elif expense_date:
            expenses_query = expenses_ref.where('expense_date', '>', expense_date).order_by('expense_date', direction=firestore.Query.DESCENDING)
        else:
            expenses_query = expenses_ref.order_by('expense_date', direction=firestore.Query.DESCENDING)
        
        expenses = [expense.to_dict() for expense in expenses_query.stream()]
        
        return expenses
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})


class Location(BaseModel):
    latitude: float
    longitude: float

class Place(BaseModel):
    location: Location
    formattedAddress: str
    googleMapsUri: str
    displayName: str

@app.post("/search-nearby", response_model=List[Place])
def search_nearby(
    included_type: Literal['parking', 'electric_vehicle_charging_station'],
    maxResultCount: int,
    latitude: float,
    longitude: float,
    radius: float,
):
    url = 'https://places.googleapis.com/v1/places:searchNearby'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': 'AIzaSyBo7u5Z2yJOZJSoP2ZwDEFYUSJ4hvNybmY',
        'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location,places.googleMapsUri'
    }
    payload = {
        "includedTypes": [included_type],
        "maxResultCount": maxResultCount,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius
            }
        },
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    data = response.json()
    results = []
    
    for place in data.get('places', []):
        location = place.get('location', {})
        latitude = location.get('latitude', 0.0)
        longitude = location.get('longitude', 0.0)
        formatted_address = place.get('formattedAddress', '')
        google_maps_uri = place.get('googleMapsUri', '')
        display_name = place.get('displayName', {}).get('text', '')

        results.append(Place(
            location=Location(latitude=latitude, longitude=longitude),
            formattedAddress=formatted_address,
            googleMapsUri=google_maps_uri,
            displayName=display_name
        ))
    
    return results

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000, ssl_keyfile='./key.pem', ssl_certfile='./cert.pem', ssl_version=ssl.PROTOCOL_TLS_SERVER)

# uvicorn main:app --reload --host 127.0.0.1 --port 8000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
