from fastapi import FastAPI, Query, Request, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
import requests

cred = credentials.Certificate('./firebase-admin-sdk.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

app = FastAPI()

origins = ["*"]

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

class ResponseUser(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    role: str
    disabled: bool


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
        api_key = "AIzaSyDv2mI6PhvFB4yCIxFsq2JmEt8Gn0aKpAQ"
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
    

class RegisterRequest(BaseModel):
    email: str
    password: str
    fullName: str
    username: str
    role: str = 'USER'
    disabled: bool = False

@app.post("/register")
async def register_user(register_request: RegisterRequest):
    try:
        user = auth.create_user(
            email=register_request.email,
            password=register_request.password,
            display_name=register_request.fullName,
            disabled=register_request.disabled
        )
        
        user_data = {
            'uid': user.uid,
            'email': register_request.email,
            'fullName': register_request.fullName,
            'username': register_request.username,
            'role': register_request.role,
            'disabled': register_request.disabled
        }
        
        db.collection('users').document(user.uid).set(user_data)
        
        return {"message": f"User {register_request.email} registered successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering user: {str(e)}")

@app.get("/getme", response_model=ResponseUser)
async def get_me(request: Request):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]

        decoded_token = auth.verify_id_token(token)
        user_uid = decoded_token.get('uid')

        user_ref = db.collection('users').document(user_uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found in the database")

        user_data = user_doc.to_dict()
        return {"user": user_data}

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token or error retrieving user: {str(e)}")


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
    

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)

# uvicorn main:app --reload --host 127.0.0.1 --port 8000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
