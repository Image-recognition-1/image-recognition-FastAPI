from fastapi import APIRouter, HTTPException, Depends, Response, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from firebase_admin import auth, firestore
import requests
from pydantic import BaseModel
from initialize_firebase import db


router = APIRouter()
db = firestore.client()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    password: str
    role: str = "USER"
    disabled: bool = False

class UserRead(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    role: str
    disabled: bool

class GoogleLoginRequest(BaseModel):
    idToken: str

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        api_key = "AIzaSyDv2mI6PhvFB4yCIxFsq2JmEt8Gn0aKpAQ"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        payload = {
            "email": form_data.username,
            "password": form_data.password,
            "returnSecureToken": True
        }
        
        api_response = requests.post(url, json=payload)
        response_data = api_response.json()
        
        if api_response.status_code != 200:
            raise HTTPException(status_code=api_response.status_code, detail=response_data.get("error", {}).get("message", "Login failed"))

        response.set_cookie(key="Token", value=response_data["idToken"], httponly=True, secure=True)
        return {"message": "Login successful"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login failed: {e}")

@router.post("/register", response_model=UserRead)
async def register_user(response: Response, register_request: RegisterRequest):
    try:
        user_data = {
            'uid': register_request.uid,
            'email': register_request.email,
            'fullName': register_request.fullName,
            'username': register_request.username,
            'role': register_request.role,
            'disabled': register_request.disabled
        }
        db.collection('users').document(register_request.uid).set(user_data)
        
        api_key = "AIzaSyDv2mI6PhvFB4yCIxFsq2JmEt8Gn0aKpAQ"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        payload = {
            "email": register_request.email,
            "password": register_request.password,
            "returnSecureToken": True
        }
        
        api_response = requests.post(url, json=payload)
        response_data = api_response.json()

        if api_response.status_code != 200:
            raise HTTPException(status_code=api_response.status_code, detail=response_data.get("error", {}).get("message", "Login failed after registration"))

        response.set_cookie(key="Token", value=response_data["idToken"], httponly=True, secure=True)

        user_ref = db.collection('users').document(register_request.uid)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_firebase = user_snapshot.to_dict()

        return {
            "uid": user_firebase["uid"],
            "email": user_firebase["email"],
            "fullName": user_firebase["fullName"],
            "username": user_firebase["username"],
            "role": user_firebase["role"],
            "disabled": user_firebase["disabled"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering user: {str(e)}")
    

@router.post("/google-login", response_model=UserRead)
async def google_login(request: Request, google_login_request: GoogleLoginRequest, response: Response):
    try:
        decoded_token = auth.verify_id_token(google_login_request.idToken)
        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        user_ref = db.collection('users').document(uid)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            user_data = {
                'uid': uid,
                'email': email,
                'fullName': decoded_token.get("name", ""),
                'username': email.split('@')[0],
                'role': 'USER',
                'disabled': False
            }
            user_ref.set(user_data)
        
        user_snapshot = user_ref.get()
        user_data = user_snapshot.to_dict()

        response.set_cookie(key="Token", value=google_login_request.idToken, httponly=True, secure=True)
        
        return UserRead(**user_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google login failed: {str(e)}")
    
    
@router.get("/logout")
async def logout(response: Response):
    try:
        response.delete_cookie(key="Token")
        return {"message": "Logout successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error logging out: {str(e)}")
