from fastapi import FastAPI, HTTPException, Depends, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from keras.applications import ResNet50
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, firestore
import requests
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet import preprocess_input, decode_predictions
import numpy as np


cred = credentials.Certificate('./firebase-admin-sdk.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Defining  fakin model

templates = Jinja2Templates(directory="templates")
model = ResNet50(weights='imagenet')


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    fullName: str
    username: str
    role: str = 'USER'
    disabled: bool = False


class ResponseUser(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    role: str
    disabled: bool


# Famozna ruta za upload slike
@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with open(file.filename, "wb") as f:
            f.write(contents)
        img = image.load_img(file.filename, target_size=(224, 224))
        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0)
        x = preprocess_input(x)
        preds = model.predict(x)
        results = decode_predictions(preds, top=3)[0]
        return templates.TemplateResponse("results.html", {"request": request, "results": results})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.post("/login")
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
            raise HTTPException(status_code=api_response.status_code, detail=response_data
                                .get("error", {}).get("message", "Login failed"))

        response.set_cookie(key="Token", value=response_data["idToken"], httponly=True, secure=True)
        
        return {"message": "Login successful"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login failed: {e}")


@app.post("/register")
async def register_user(response: Response, register_request: RegisterRequest):
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
            raise HTTPException(status_code=api_response.status_code, detail=response_data.get("error", {})
                                .get("message", "Login failed after registration"))

        response.set_cookie(key="Token", value=response_data["idToken"], httponly=True, secure=True)
        
        return {"message": f"User {register_request.email} registered and logged in successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering user: {str(e)}")


@app.get("/getme", response_model=ResponseUser)
async def get_me(request: Request):
    try:
        token = request.cookies.get("Token")
        if not token:
            raise HTTPException(status_code=401, detail="Token not found in cookies")

        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get('uid')

        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_ref = db.collection('users').document(uid)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_snapshot.to_dict()

        response_user = ResponseUser(
            uid=user_data['uid'],
            email=user_data['email'],
            fullName=user_data['fullName'],
            username=user_data['username'],
            role=user_data['role'],
            disabled=user_data['disabled']
        )
        
        return response_user

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving user: {str(e)}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
